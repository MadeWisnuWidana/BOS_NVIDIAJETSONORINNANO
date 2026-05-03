"""
╔══════════════════════════════════════════════════════════════════╗
║   FER Publisher — BRONE Patched Version                          ║
║   Drop-in replacement untuk FER-BRONE/publisher.py              ║
║                                                                  ║
║   Perubahan dari versi asli:                                     ║
║     1. Topic publish: robot/fer_emotion  (bukan robot/expression)║
║     2. Payload tambah field "expression" (mapped dari emotion)   ║
║     3. Publish gaze XY dari bbox → robot/fer_gaze               ║
║     4. Subscribe robot/mode → aktif hanya saat mirror/conv mode  ║
║                                                                  ║
║   Cara pakai:                                                    ║
║     Copy file ini ke folder FER-BRONE/, lalu:                   ║
║       python3 publisher_brone.py                                 ║
║     Atau biarkan main-entry.py yang menjalankannya otomatis.     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import cv2
import numpy as np
import onnxruntime as ort
import os
import time
import json
import paho.mqtt.client as mqtt
from collections import deque

# ==================== CONFIGURATION ====================
class Config:
    # --- MODEL SETTINGS ---
    # Cari model di direktori yang sama dengan script ini
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_PATH = os.path.join(_SCRIPT_DIR, 'fer_resnet34_v1.2.onnx')

    # Haarcascade fallback
    CASCADE_PATH = os.path.join(_SCRIPT_DIR, 'haarcascades', 'haarcascade_frontalface_default.xml')
    if not os.path.exists(CASCADE_PATH):
        CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'

    # Model classes — sesuaikan dengan model .onnx kamu
    EMOTION_LABELS = ['Upset', 'Shocked', 'Happy', 'Sad', 'Neutral']
    INPUT_SIZE = 112

    # Smoothing
    WINDOW_SIZE = 30
    CONFIDENCE_THRESHOLD = 0.50

    # --- MQTT TOPICS (PATCHED) ---
    MQTT_BROKER      = "localhost"
    MQTT_PORT        = 1883
    TOPIC_EMOTION    = "robot/fer_emotion"   # ← Baru (bukan robot/expression)
    TOPIC_GAZE       = "robot/fer_gaze"      # ← Baru
    TOPIC_MODE       = "robot/mode"          # ← Subscribe ini untuk auto-standby

    # --- EMOTION → DISPLAY EXPRESSION MAPPING ---
    EMOTION_TO_EXPRESSION = {
        'Happy':   'happier',
        'Neutral': 'idle',
        'Sad':     'sad',
        'Shocked': 'shock',
        'Upset':   'cry',          # Sprint 2: akan diganti 'angry' jika ditambahkan
    }


# ==================== UTILS ====================
def softmax(x):
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=1, keepdims=True)


def preprocess_image(face_img):
    img = cv2.resize(face_img, (Config.INPUT_SIZE, Config.INPUT_SIZE))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img  = (img - mean) / std
    img  = img.transpose(2, 0, 1)
    img  = np.expand_dims(img, axis=0)
    return img


class TemporalAveraging:
    def __init__(self, window_size=15, confidence_threshold=0.5):
        self.window_size          = window_size
        self.confidence_threshold = confidence_threshold
        self.buffer               = deque(maxlen=window_size)

    def add_prediction(self, probabilities):
        self.buffer.append(probabilities)

    def get_averaged_emotion(self):
        if len(self.buffer) < 2:
            return "Collecting...", 0.0
        avg_probs = np.mean(self.buffer, axis=0)
        idx  = np.argmax(avg_probs)
        conf = float(np.max(avg_probs))
        if conf >= self.confidence_threshold:
            return Config.EMOTION_LABELS[idx], conf
        return "UNCERTAIN", conf

    def reset(self):
        self.buffer.clear()


# ==================== PUBLISHER SYSTEM ====================
class BroneFERPublisher:
    def __init__(self):
        print("=" * 55)
        print("  FER Publisher — BRONE Patched")
        print("=" * 55)

        # State: hanya proses saat mode aktif
        self.active_mode = None   # None = standby, 'mirror' / 'conversation' = aktif
        self.running     = True

        # 1. MQTT
        self._setup_mqtt()

        # 2. ONNX Model
        self._load_model()

        # 3. Camera + Smoothing
        self.face_cascade  = cv2.CascadeClassifier(Config.CASCADE_PATH)
        self.temporal_avg  = TemporalAveraging(Config.WINDOW_SIZE, Config.CONFIDENCE_THRESHOLD)
        self.no_face_count = 0
        self.prev_time     = time.time()
        self.fps           = 0.0

    # ── MQTT ────────────────────────────────────────────────────
    def _setup_mqtt(self):
        print(f"  Menghubungkan ke broker {Config.MQTT_BROKER}:{Config.MQTT_PORT}...")
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.on_connect    = self._on_connect
            self.client.on_message    = self._on_message
            self.client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, 60)
            self.client.loop_start()
            time.sleep(0.8)
            print("  ✓ MQTT terhubung")
        except Exception as e:
            print(f"  ✗ Gagal konek MQTT: {e}")
            print("    Pastikan Mosquitto berjalan: sudo systemctl start mosquitto")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            # Subscribe ke topic mode agar bisa auto-standby
            client.subscribe(Config.TOPIC_MODE)
            print(f"  ✓ Subscribe ke {Config.TOPIC_MODE}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            mode    = payload.get("mode", "")

            if mode in ("mirror", "conversation"):
                if self.active_mode != mode:
                    print(f"\n  [Mode] Aktif: {mode.upper()} — FER mulai memproses")
                    self.active_mode = mode
            else:
                # default / unknown → standby
                if self.active_mode is not None:
                    print(f"\n  [Mode] Standby — FER berhenti publish")
                    self.active_mode = None
                    self.temporal_avg.reset()
        except Exception:
            pass

    # ── Model ───────────────────────────────────────────────────
    def _load_model(self):
        if not os.path.exists(Config.MODEL_PATH):
            # Coba folder models/
            alt = os.path.join(os.path.dirname(Config.MODEL_PATH), 'models',
                               os.path.basename(Config.MODEL_PATH))
            if os.path.exists(alt):
                Config.MODEL_PATH = alt
            else:
                print(f"  ✗ Model tidak ditemukan: {Config.MODEL_PATH}")
                raise FileNotFoundError(Config.MODEL_PATH)

        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        self.session   = ort.InferenceSession(Config.MODEL_PATH, providers=providers)
        self.input_name  = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        print(f"  ✓ Model dimuat ({self.session.get_providers()[0]})")

    # ── Publish Helpers ──────────────────────────────────────────
    def _publish_emotion(self, emotion: str, confidence: float):
        """Publish emotion + mapped expression ke robot/fer_emotion."""
        if emotion in ("UNCERTAIN", "Collecting...", "Analyzing..."):
            return
        if self.active_mode not in ("mirror", "conversation"):
            return

        payload = json.dumps({
            "timestamp":  time.time(),
            "emotion":    emotion,
            "expression": Config.EMOTION_TO_EXPRESSION.get(emotion, 'idle'),
            "confidence": round(confidence, 2)
        })
        self.client.publish(Config.TOPIC_EMOTION, payload)

    def _publish_gaze(self, x: int, y: int, w: int, h: int,
                      frame_w: int, frame_h: int):
        """Estimasi gaze dari posisi bbox wajah → publish ke robot/fer_gaze."""
        if self.active_mode not in ("mirror", "conversation"):
            return

        # Center wajah (0..1)
        center_x = (x + w / 2) / frame_w
        center_y = (y + h / 2) / frame_h

        # Normalize ke [-1, 1], mirror horizontal (robot hadap pengguna)
        gaze_x = (center_x - 0.5) * -2.0
        gaze_y = (center_y - 0.5) *  2.0

        # Clamp
        gaze_x = max(-1.0, min(1.0, gaze_x))
        gaze_y = max(-1.0, min(1.0, gaze_y))

        payload = json.dumps({
            "gaze_x":       round(gaze_x, 3),
            "gaze_y":       round(gaze_y, 3),
            "face_detected": True,
            "timestamp":    time.time()
        })
        self.client.publish(Config.TOPIC_GAZE, payload)

    def _publish_no_face(self):
        """Beritahu display bahwa wajah tidak terdeteksi."""
        if self.active_mode not in ("mirror", "conversation"):
            return
        payload = json.dumps({"face_detected": False, "timestamp": time.time()})
        self.client.publish(Config.TOPIC_GAZE, payload)

    # ── UI Helpers ───────────────────────────────────────────────
    def _draw_ui(self, frame, x, y, w, h,
                 inst_emo, inst_conf, smooth_emo, smooth_conf):
        white  = (255, 255, 255)
        green  = (0, 255, 0)
        orange = (0, 165, 255)
        red    = (0, 0, 255)

        if smooth_emo in ("Neutral", "Happy"):
            col = green
        elif smooth_emo in ("Upset", "Sad", "Shocked"):
            col = red
        else:
            col = orange

        # Panel
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (430, 190), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, f"Instant : {inst_emo} ({inst_conf:.2f})",
                    (25, 45), font, 0.6, white, 1, cv2.LINE_AA)
        cv2.putText(frame, f"Smoothed: {smooth_emo} ({smooth_conf:.2f})",
                    (25, 80), font, 0.6, col, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Mode    : {self.active_mode or 'STANDBY'}",
                    (25, 115), font, 0.6, orange if self.active_mode else white, 1, cv2.LINE_AA)
        cv2.putText(frame, f"FPS     : {self.fps:.1f}",
                    (25, 150), font, 0.6, white, 1, cv2.LINE_AA)

        # Indikator publish (hijau = publishing, abu = standby)
        pub_color = green if self.active_mode else (80, 80, 80)
        cv2.circle(frame, (410, 80), 8, pub_color, -1)

        # Kotak wajah
        cv2.rectangle(frame, (x, y), (x + w, y + h), col, 2)
        label = f"{smooth_emo}"
        (tw, _), _ = cv2.getTextSize(label, font, 0.7, 2)
        cv2.rectangle(frame, (x, y - 35), (x + tw + 10, y), col, -1)
        cv2.putText(frame, label, (x + 5, y - 10), font, 0.7, (0, 0, 0), 2)

        return frame

    # ── Main Loop ────────────────────────────────────────────────
    def run(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        if not cap.isOpened():
            print("  ✗ Gagal membuka webcam.")
            return

        print("  ✓ Webcam aktif. Tekan 'q' untuk keluar.\n")
        print("  [Menunggu mode dari main-entry / MQTT...]\n")

        while self.running:
            ret, frame = cap.read()
            if not ret:
                break

            # FPS
            now       = time.time()
            self.fps  = 1.0 / max(now - self.prev_time, 1e-6)
            self.prev_time = now

            frame = cv2.flip(frame, 1)
            fh, fw = frame.shape[:2]
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))

            if len(faces) > 0:
                self.no_face_count = 0
                x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
                face_roi   = frame[y:y + h, x:x + w]

                try:
                    inp   = preprocess_image(face_roi)
                    logits = self.session.run([self.output_name], {self.input_name: inp})[0]
                    probs  = softmax(logits)[0]

                    inst_idx  = int(np.argmax(probs))
                    inst_emo  = Config.EMOTION_LABELS[inst_idx]
                    inst_conf = float(np.max(probs))

                    self.temporal_avg.add_prediction(probs)
                    smooth_emo, smooth_conf = self.temporal_avg.get_averaged_emotion()

                    # Publish (only when active mode)
                    self._publish_emotion(smooth_emo, smooth_conf)
                    self._publish_gaze(x, y, w, h, fw, fh)

                    frame = self._draw_ui(frame, x, y, w, h,
                                         inst_emo, inst_conf,
                                         smooth_emo, smooth_conf)
                except Exception as e:
                    print(f"  [Error inference] {e}")

            else:
                self.no_face_count += 1
                if self.no_face_count > 10:
                    self.temporal_avg.reset()
                    self._publish_no_face()

                cv2.putText(frame, "Mencari wajah...", (25, 115),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (180, 180, 180), 2)
                cv2.putText(frame, f"FPS: {self.fps:.1f}", (25, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 1)
                cv2.putText(frame, f"Mode: {self.active_mode or 'STANDBY'}", (25, 45),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 165, 255), 1)

            cv2.imshow("FER Publisher — BRONE", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.running = False

        cap.release()
        cv2.destroyAllWindows()
        self.client.loop_stop()
        self.client.disconnect()
        print("  FER Publisher selesai.")


if __name__ == "__main__":
    app = BroneFERPublisher()
    app.run()
