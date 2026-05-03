# 04 · FER Pipeline — Facial Emotion Recognition

← [03 · Gaze Tracking](03-gaze-tracking.md) | [05 · MQTT Protocol →](05-mqtt-protocol.md)

---

## Daftar Isi

- [Overview & Varian Sistem](#overview--varian-sistem)
- [Model Architecture (ResNet34)](#model-architecture-resnet34)
- [Preprocessing Pipeline](#preprocessing-pipeline)
- [Temporal Averaging Algorithm](#temporal-averaging-algorithm)
- [Emotion → Expression Mapping](#emotion--expression-mapping)
- [Gaze Estimation dari Bounding Box](#gaze-estimation-dari-bounding-box)
- [Mode-Awareness: Standby Logic](#mode-awareness-standby-logic)
- [publisher_brone.py — Alur Lengkap](#publisher_bronepy--alur-lengkap)
- [Perbedaan pub.py vs publisher_brone.py](#perbedaan-pubpy-vs-publisher_bronepy)

---

## Overview & Varian Sistem

BRONE memiliki dua varian FER publisher tergantung hardware:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Varian 1: pub.py (Intel/Laptop — PyTorch)                         │
│                                                                     │
│  Model: fer_model_v1.2_fusion_colab.pth                            │
│  Framework: PyTorch + torchvision                                  │
│  Backbone: ResNet34 (pretrained ImageNet, fine-tuned FER)          │
│  Device: CUDA jika tersedia, fallback CPU                          │
│  Use case: Development/testing di laptop Intel                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Varian 2: publisher_brone.py (Jetson — ONNX Runtime)              │
│                                                                     │
│  Model: fer_resnet34_v1.2.onnx                                     │
│  Framework: ONNX Runtime (ort)                                     │
│  Provider: CUDAExecutionProvider → fallback CPUExecutionProvider   │
│  Mode-aware: subscribe robot/mode, standby jika mode=default       │
│  Use case: Production di NVIDIA Jetson                             │
└─────────────────────────────────────────────────────────────────────┘
```

**Mengapa ONNX di Jetson?**
- PyTorch di Jetson lebih berat dan versi kompatibilitas sering bermasalah
- ONNX Runtime dengan TensorRT backend lebih efisien di GPU Jetson
- Model ONNX bisa di-quantize (INT8) untuk performa lebih tinggi

---

## Model Architecture (ResNet34)

```
Input: RGB image 112×112×3

ResNet34 Backbone:
  Conv1 → BN → ReLU → MaxPool
      │
      ├── Layer1: [3×3, 64] × 3 blocks
      ├── Layer2: [3×3, 128] × 4 blocks
      ├── Layer3: [3×3, 256] × 6 blocks
      └── Layer4: [3×3, 512] × 3 blocks
              │
              ▼
         AdaptiveAvgPool → [512]
              │
              ▼
         Custom FC Head:
           Dropout(0.5)
           Linear(512 → 256)
           ReLU
           Dropout(0.3)
           Linear(256 → 5)    ← 5 kelas emosi
              │
              ▼
         Logits [5]  (sebelum softmax)

Kelas Output (urutan tetap):
  Index 0: 'Upset'    (marah/kesal)
  Index 1: 'Shocked'  (terkejut)
  Index 2: 'Happy'    (senang)
  Index 3: 'Sad'      (sedih)
  Index 4: 'Neutral'  (netral)
```

---

## Preprocessing Pipeline

```
Webcam frame (BGR, 1280×720)
        │
        ▼
cv2.flip(frame, 1)                  ← mirror horizontal
        │
        ▼
HaarCascade detectMultiScale:
  gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
  faces = cascade.detectMultiScale(gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60))
        │
        │  [x, y, w, h] per wajah
        │  Pilih wajah terbesar: max(faces, key=lambda b: b[2]*b[3])
        ▼
face_roi = frame[y:y+h, x:x+w]      ← crop wajah
        │
        ▼
PyTorch path (pub.py):
  cv2.cvtColor(face_roi, BGR→RGB)
  transforms.Resize((112, 112))
  transforms.ToTensor()              ← [0,255] → [0.0,1.0]
  transforms.Normalize(
    mean=[0.485, 0.456, 0.406],      ← ImageNet stats
    std =[0.229, 0.224, 0.225]
  )
  unsqueeze(0)                       ← add batch dim → [1,3,112,112]
        │
        ▼
model(input_tensor) → logits [1,5]
softmax(logits, dim=1) → probs [0.1, 0.6, 0.1, 0.1, 0.1]

ONNX path (publisher_brone.py):
  cv2.resize(face_roi, (112, 112))
  cv2.cvtColor(BGR→RGB)
  img = img.astype(np.float32) / 255.0
  img = (img - mean) / std           ← manual normalize
  img = img.transpose(2,0,1)         ← HWC → CHW
  img = np.expand_dims(img, axis=0)  ← [1,3,112,112]
        │
        ▼
session.run([output_name], {input_name: img}) → logits [1,5]
softmax(logits) → probs [5]
```

---

## Temporal Averaging Algorithm

### Masalah: Flickering Ekspresi

Tanpa smoothing, model menghasilkan prediksi yang berfluktuasi antar frame:

```
Frame:   1    2    3    4    5    6    7    8    9    10
Result: Sad  Sad Happy Sad  Sad  Sad Happy Sad  Sad  Sad
                 ↑               ↑
           False positive — robot ekspresi berubah setiap 200ms
```

### Solusi: Sliding Window Average

```
WINDOW_SIZE = 30 (frame)  ← buffer 30 prediksi terakhir

Buffer (deque, maxlen=30):
  Frame 1:  [0.1, 0.05, 0.1, 0.7, 0.05]  ← Sad dominan
  Frame 2:  [0.1, 0.05, 0.1, 0.7, 0.05]
  Frame 3:  [0.05, 0.05, 0.8, 0.05, 0.05] ← Happy spike
  Frame 4:  [0.1, 0.05, 0.1, 0.7, 0.05]
  ...
  Frame 30: [0.1, 0.05, 0.1, 0.7, 0.05]

np.mean(buffer, axis=0):
  [0.097, 0.051, 0.137, 0.662, 0.053]
         ↑                 ↑
  Shocked kecil      Sad dominan (0.66)
  
  Prediction: "Sad", confidence=0.662 ≥ 0.50 → PUBLISH ✓
```

### Algoritma `TemporalAveraging`

```python
class TemporalAveraging:
    def __init__(self, window_size=30, confidence_threshold=0.50):
        self.buffer = deque(maxlen=window_size)

    def add_prediction(self, probs):     # probs: numpy array [5]
        self.buffer.append(probs)

    def get_averaged_emotion(self):
        if len(self.buffer) < 2:
            return "Collecting...", 0.0   # ← belum cukup data

        avg_probs = np.mean(self.buffer, axis=0)  # rata-rata semua frame
        idx  = np.argmax(avg_probs)               # kelas tertinggi
        conf = float(np.max(avg_probs))           # nilai tertinggi

        if conf >= self.confidence_threshold:     # 0.50
            return EMOTION_LABELS[idx], conf
        else:
            return "UNCERTAIN", conf              # ← jangan publish

    def reset(self):
        self.buffer.clear()   # dipanggil saat wajah hilang > 10 frame

Flow:
  Wajah terdeteksi:
    add_prediction(probs)
    emotion, conf = get_averaged_emotion()
    if emotion not in ("UNCERTAIN", "Collecting..."):
        publish_emotion(emotion, conf)

  Wajah hilang > 10 frame:
    temporal_avg.reset()
    publish_no_face()
```

### Timeline Buffer

```
Frame:  1   2   3  ...  28  29  30  31  32
Buffer: [1] [2] [3] ... [28][29][30][31][32]
                              ↑          ↑
                        frame 1 dibuang  frame 32 masuk
                        (deque maxlen=30)

Setelah 30 frame: buffer selalu berisi 30 prediksi terbaru
```

---

## Emotion → Expression Mapping

```
ML Model Output           Canvas State
(psikologis)              (visual)
──────────────────────────────────────────

'Happy'    ──────────────▶  'happier'
           (senang besar)   (senyum + sparkle + blush)

'Neutral'  ──────────────▶  'idle'
           (netral)         (senyum biasa)

'Sad'      ──────────────▶  'sad'
           (sedih)          (mulut frown)

'Shocked'  ──────────────▶  'shock'
           (terkejut)       (mulut O besar)

'Upset'    ──────────────▶  'cry'
           (kesal/marah)    (air mata + wave eye)
           *Catatan: 'angry' belum diimplementasi,
            sementara pakai 'cry' sebagai proxy*
```

**Mengapa 'Upset' → 'cry' bukan 'angry'?**

```
Alasan teknis:
  - Ekspresi 'angry' belum di-implementasi di Canvas
  - 'Upset' dalam dataset training mencakup keduanya (kesal dan sedih)
  - Sebagai temporary placeholder

Roadmap:
  Sprint 2: Tambah ekspresi 'angry' di fr-mouths.js
  Update mapping: 'Upset' → 'angry'
  Lihat: docs/02-face-rendering.md#cara-menambah-ekspresi-baru
```

---

## Gaze Estimation dari Bounding Box

Di `mirror`/`conversation` mode, Python mengambil alih estimasi gaze menggunakan bounding box wajah:

```
Bounding Box dari HaarCascade: (x, y, w, h)
  x, y  = pojok kiri atas wajah
  w, h  = lebar dan tinggi kotak wajah

Step 1: Hitung center wajah (dalam pixel)
  face_cx = x + w/2
  face_cy = y + h/2

Step 2: Normalize ke [0, 1]
  center_x = face_cx / frame_width   ∈ [0, 1]
  center_y = face_cy / frame_height  ∈ [0, 1]

Step 3: Normalize ke [-1, 1] dan mirror
  gaze_x = (center_x - 0.5) × -2.0  ← mirror horizontal
  gaze_y = (center_y - 0.5) ×  2.0  ← tidak di-mirror

Step 4: Clamp
  gaze_x = max(-1.0, min(1.0, gaze_x))
  gaze_y = max(-1.0, min(1.0, gaze_y))

Step 5: Publish ke robot/fer_gaze
  payload = {
    "gaze_x": round(gaze_x, 3),
    "gaze_y": round(gaze_y, 3),
    "face_detected": True,
    "timestamp": time.time()
  }
```

**Keterbatasan vs MediaPipe:**
- HaarCascade hanya memberikan lokasi wajah (bukan keypoints mata spesifik)
- Gaze estimation kurang presisi dibanding MediaPipe
- Trade-off diterima karena: Python butuh akses kamera untuk FER

---

## Mode-Awareness: Standby Logic

`publisher_brone.py` dapat menjalankan inferensi setiap frame, tapi hanya mem-publish data saat mode aktif. Ini menghemat bandwidth MQTT dan menghindari efek samping di `default` mode.

```
publisher_brone.py berjalan:

  Startup → active_mode = None (standby)

  ┌─────────────────────────────────────────────────────┐
  │  Main Loop (cap.read() setiap frame)                │
  │                                                     │
  │  1. Baca frame kamera                               │
  │  2. Deteksi wajah (HaarCascade)                     │
  │  3. Inferensi FER (ONNX)                            │
  │  4. Temporal averaging                              │
  │                                                     │
  │  5. Cek active_mode:                                │
  │      if active_mode in ('mirror', 'conversation'): │
  │          _publish_emotion()  ← publish              │
  │          _publish_gaze()     ← publish              │
  │      else:                                         │
  │          pass  ← STANDBY, tidak publish             │
  │                                                     │
  │  6. Tampilkan frame di OpenCV window                │
  └─────────────────────────────────────────────────────┘

  Paralel — Thread MQTT subscribed ke robot/mode:
    on_message():
      mode = payload['mode']
      if mode in ('mirror', 'conversation'):
          active_mode = mode      ← mulai publish
          print("[Mode] Aktif: MIRROR — FER mulai memproses")
      else:
          active_mode = None      ← standby
          temporal_avg.reset()   ← bersihkan buffer
```

---

## publisher_brone.py — Alur Lengkap

```
python3 publisher_brone.py
        │
        ├── BroneFERPublisher.__init__()
        │       │
        │       ├── _setup_mqtt()
        │       │       ├── mqtt.Client(VERSION2)
        │       │       ├── client.connect("localhost", 1883)
        │       │       ├── client.loop_start()            ← thread MQTT
        │       │       └── client.subscribe("robot/mode") ← listen mode
        │       │
        │       ├── _load_model()
        │       │       ├── ort.InferenceSession(model.onnx,
        │       │       │     providers=['CUDAExecutionProvider',
        │       │       │                'CPUExecutionProvider'])
        │       │       └── print(session.get_providers()[0])  ← konfirmasi GPU/CPU
        │       │
        │       └── cv2.CascadeClassifier(cascade_path)
        │
        ├── run()
        │       │
        │       ├── cap = cv2.VideoCapture(0)
        │       │     cap.set(FRAME_WIDTH, 1280)
        │       │     cap.set(FRAME_HEIGHT, 720)
        │       │
        │       └── MAIN LOOP:
        │             │
        │             ├── ret, frame = cap.read()
        │             ├── FPS calculation
        │             ├── frame = cv2.flip(frame, 1)
        │             ├── gray = cvtColor(BGR→GRAY)
        │             │
        │             ├── faces = detectMultiScale(gray, 1.1, 5, (60,60))
        │             │
        │             ├── if faces detected:
        │             │       x, y, w, h = largest_face
        │             │       face_roi = frame[y:y+h, x:x+w]
        │             │       inp = preprocess_image(face_roi)
        │             │       logits = session.run([out_name], {in_name: inp})
        │             │       probs = softmax(logits)[0]
        │             │       inst_emo, inst_conf = argmax(probs)
        │             │       temporal_avg.add_prediction(probs)
        │             │       smooth_emo, smooth_conf = get_averaged_emotion()
        │             │       _publish_emotion(smooth_emo, smooth_conf)
        │             │       _publish_gaze(x, y, w, h, fw, fh)
        │             │       _draw_ui(frame, ...)
        │             │
        │             ├── else (no face):
        │             │       no_face_count += 1
        │             │       if no_face_count > 10:
        │             │           temporal_avg.reset()
        │             │           _publish_no_face()
        │             │
        │             ├── cv2.imshow("FER Publisher — BRONE", frame)
        │             └── if 'q' pressed → break
        │
        └── Cleanup:
              cap.release()
              cv2.destroyAllWindows()
              client.loop_stop()
              client.disconnect()
```

---

## Perbedaan pub.py vs publisher_brone.py

| Aspek | `pub.py` | `publisher_brone.py` |
|-------|----------|---------------------|
| Framework | PyTorch | ONNX Runtime |
| Model file | `.pth` | `.onnx` |
| Mode-aware | ❌ selalu publish | ✅ standby jika default |
| Gaze publish | ❌ tidak | ✅ robot/fer_gaze |
| Topic publish | `robot/fer_emotion` | `robot/fer_emotion` + `robot/fer_gaze` |
| Subscribe | ❌ tidak | ✅ robot/mode |
| Debug UI | Minimal | Lengkap (mode indicator, FPS, conf) |
| Target hardware | Intel/laptop | NVIDIA Jetson |
| Payload `expression` | ✅ ada | ✅ ada |

---

← [03 · Gaze Tracking](03-gaze-tracking.md) | [05 · MQTT Protocol →](05-mqtt-protocol.md)
