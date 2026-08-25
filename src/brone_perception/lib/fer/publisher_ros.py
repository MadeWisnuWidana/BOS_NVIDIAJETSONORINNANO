"""
FER Publisher — BRONE ROS 2 Patched Version
Mendengarkan /image_raw dari ROS 2, bukan membuka webcam OpenCV.
"""
import cv2
import numpy as np
import onnxruntime as ort
import os
import time
import json
import paho.mqtt.client as mqtt
from collections import deque
import threading

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

# ==================== CONFIGURATION ====================
class Config:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_PATH = '/home/brone/brone_vision_ws/src/brone_perception/models/fer_resnet34_v1.2.onnx'

    CASCADE_PATH = os.path.join(_SCRIPT_DIR, 'haarcascades', 'haarcascade_frontalface_default.xml')
    if not os.path.exists(CASCADE_PATH):
        CASCADE_PATH = '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml'

    EMOTION_LABELS = ['Upset', 'Shocked', 'Happy', 'Sad', 'Neutral']
    INPUT_SIZE = 112

    WINDOW_SIZE = 30
    CONFIDENCE_THRESHOLD = 0.40

    MQTT_BROKER      = "localhost"
    MQTT_PORT        = 1883
    TOPIC_EMOTION    = "robot/fer_emotion"
    TOPIC_GAZE       = "robot/fer_gaze"
    TOPIC_MODE       = "robot/mode"

    EMOTION_TO_EXPRESSION = {
        'Happy':   'happier',
        'Neutral': 'idle',
        'Sad':     'sad',
        'Shocked': 'shock',
        'Upset':   'cry',
    }

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

class BroneFERNode(Node):
    def __init__(self):
        super().__init__('brone_fer_publisher')
        self.get_logger().info("=" * 55)
        self.get_logger().info("  FER Publisher — BRONE ROS 2 Patched")
        self.get_logger().info("=" * 55)

        self.active_mode = 'default'
        self.bridge = CvBridge()
        
        self._setup_mqtt()
        self._load_model()
        
        self.face_cascade  = cv2.CascadeClassifier(Config.CASCADE_PATH)
        self.temporal_avg  = TemporalAveraging(Config.WINDOW_SIZE, Config.CONFIDENCE_THRESHOLD)
        self.no_face_count = 0
        self.prev_time     = time.time()
        self.fps           = 0.0

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.sub = self.create_subscription(Image, '/image_raw', self.image_callback, qos)

    def _setup_mqtt(self):
        self.get_logger().info(f"Menghubungkan ke broker {Config.MQTT_BROKER}:{Config.MQTT_PORT}...")
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.on_connect    = self._on_connect
            self.client.on_message    = self._on_message
            self.client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, 60)
            self.client.loop_start()
            self.get_logger().info("MQTT terhubung")
        except Exception as e:
            self.get_logger().error(f"Gagal konek MQTT: {e}")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.subscribe(Config.TOPIC_MODE)
            self.get_logger().info(f"Subscribe ke {Config.TOPIC_MODE}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            mode    = payload.get("mode", "")
            if mode in ("mirror", "conversation", "eyefollow"):
                if self.active_mode != mode:
                    self.get_logger().info(f"[Mode] Aktif: {mode.upper()} — FER memproses")
                    self.active_mode = mode
            else:
                if self.active_mode != 'default':
                    self.get_logger().info(f"[Mode] Standby — FER berhenti publish")
                    self.active_mode = 'default'
                    self.temporal_avg.reset()
        except Exception:
            pass

    def _load_model(self):
        if not os.path.exists(Config.MODEL_PATH):
            alt = os.path.join(os.path.dirname(Config.MODEL_PATH), 'models', os.path.basename(Config.MODEL_PATH))
            if os.path.exists(alt):
                Config.MODEL_PATH = alt
            else:
                self.get_logger().error(f"Model tidak ditemukan: {Config.MODEL_PATH}")
                raise FileNotFoundError(Config.MODEL_PATH)
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        self.session   = ort.InferenceSession(Config.MODEL_PATH, providers=providers)
        self.input_name  = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.get_logger().info(f"Model dimuat ({self.session.get_providers()[0]})")

    def _publish_emotion(self, emotion: str, confidence: float):
        if emotion in ("UNCERTAIN", "Collecting...", "Analyzing..."):
            return
        if self.active_mode not in ['mirror', 'conversation', 'eyefollow']:
            return
        payload = json.dumps({
            "timestamp":  time.time(),
            "emotion":    emotion,
            "expression": Config.EMOTION_TO_EXPRESSION.get(emotion, 'idle'),
            "confidence": round(confidence, 2)
        })
        self.client.publish(Config.TOPIC_EMOTION, payload)

    def _publish_gaze(self, x: int, y: int, w: int, h: int, frame_w: int, frame_h: int):
        center_x = (x + w / 2) / frame_w
        center_y = (y + h / 2) / frame_h
        gaze_x = (center_x - 0.5) *  2.0
        gaze_y = (center_y - 0.5) *  2.0
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
        payload = json.dumps({"face_detected": False, "timestamp": time.time()})
        self.client.publish(Config.TOPIC_GAZE, payload)

    def image_callback(self, msg):
        now = time.time()
        self.fps = 1.0 / max(now - self.prev_time, 1e-6)
        self.prev_time = now

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f"CVBridge error: {e}")
            return

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

                self._publish_emotion(smooth_emo, smooth_conf)
                self._publish_gaze(x, y, w, h, fw, fh)
            except Exception as e:
                pass
        else:
            self.no_face_count += 1
            if self.no_face_count > 10:
                self.temporal_avg.reset()
                self._publish_no_face()

def main(args=None):
    rclpy.init(args=args)
    node = BroneFERNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.client.loop_stop()
        node.client.disconnect()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
