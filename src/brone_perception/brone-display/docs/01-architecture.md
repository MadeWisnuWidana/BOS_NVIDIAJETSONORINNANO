# 01 · Arsitektur Sistem & Mode Operasi

← [README](../README.md) | [02 · Face Rendering →](02-face-rendering.md)

---

## Daftar Isi

- [Konsep & Filosofi Desain](#konsep--filosofi-desain)
- [Topologi Sistem](#topologi-sistem)
- [State Machine Mode Operasi](#state-machine-mode-operasi)
- [Alur Data End-to-End](#alur-data-end-to-end)
- [Struktur File Lengkap](#struktur-file-lengkap)
- [Dependency Loading Order](#dependency-loading-order)
- [Mekanisme Switch Kamera](#mekanisme-switch-kamera)

---

## Konsep & Filosofi Desain

BRONE dibangun di atas tiga prinsip:

1. **Separation of Concerns**: Rendering (Canvas), tracking (MediaPipe), komunikasi (MQTT), dan AI (Python FER) berjalan sebagai modul terpisah yang berkomunikasi lewat pesan.
2. **Camera Arbitration**: Hanya satu proses boleh memegang kamera fisik pada satu waktu. Mode operasi menentukan siapa pemilik kamera.
3. **Hardware Decoupling**: Servo leher robot menerima perintah angle via MQTT — tidak pernah di-hardcode ke kode rendering.

---

## Topologi Sistem

```
╔════════════════════════════════════════════════════════════════════╗
║                     BROWSER (Chromium / Kiosk)                    ║
║                                                                    ║
║  ┌─────────────────┐   gaze {x,y}   ┌─────────────────────────┐  ║
║  │  face-tracker.js │──────────────▶│        app.js            │  ║
║  │                 │                │  (Orchestrator / Logic)  │  ║
║  │  MediaPipe      │                │                         │  ║
║  │  Face Detection │                │  • Mode State Machine    │  ║
║  │  (model: short) │                │  • Head Pan Algorithm    │  ║
║  └─────────────────┘                │  • MQTT Message Router   │  ║
║         ▲                           └────────────┬────────────┘  ║
║    video │                               state ↓  │ publish       ║
║    feed  │                          ┌────────────▼────────────┐  ║
║  ┌───────┴───────┐                  │    face-renderer.js     │  ║
║  │    Webcam     │                  │  (Canvas Drawing Loop)  │  ║
║  └───────────────┘                  └─────────────────────────┘  ║
║                                                 │                 ║
║                                    ┌────────────▼────────────┐   ║
║                                    │     mqtt-client.js      │   ║
║                                    │  (Paho WebSocket)       │   ║
║                                    └────────────┬────────────┘   ║
╚════════════════════════════════════════════════│════════════════╝
                                                  │ WebSocket
                                                  │ port 9001
                            ┌─────────────────────▼──────────────────┐
                            │         Mosquitto MQTT Broker           │
                            │                                         │
                            │  port 1883 ────────────── port 9001    │
                            │  (native TCP)         (WebSocket)      │
                            └──────┬──────────────────────────────────┘
                                   │ MQTT port 1883
               ┌───────────────────┼───────────────────┐
               │                   │                   │
  ┌────────────▼──────┐  ┌─────────▼──────┐  ┌────────▼───────────┐
  │ publisher_brone.py│  │main-entry.py   │  │ test_tts_publisher │
  │ (FER AI pipeline) │  │ (CLI Launcher) │  │ (Debug/Test tool)  │
  │                   │  │                │  └────────────────────┘
  │ • OpenCV webcam   │  │ • HTTP server  │
  │ • ResNet34/ONNX   │  │ • FER spawn    │
  │ • Temporal avg    │  │ • Mode control │
  │ • publish emosi   │  └────────────────┘
  │ • publish gaze    │
  └───────────────────┘
           │ robot/head_control
  ┌────────▼───────────┐
  │  Robot Servo (HW)  │
  │  Head Pan Motor    │
  └────────────────────┘
```

---

## State Machine Mode Operasi

```
                      ┌──────────────────────────────┐
                      │  STARTUP / Initial State       │
                      │  • HTTP server naik            │
                      │  • MQTT connect                │
                      │  • Browser load                │
                      └──────────────┬───────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │          DEFAULT MODE           │
                    │                                 │
                    │  • Browser pegang kamera        │
                    │  • MediaPipe aktif              │
                    │  • Robot idle (senyum)          │
                    │  • Gaze tracking dari browser   │
                    │  • FER Python: standby/off      │
                    │  • Terima: robot/expression     │
                    └────────┬──────────────┬─────────┘
                             │              │
                  press M / MQTT mode=mirror│  press C / MQTT mode=conversation
                             │              │
              ┌──────────────▼──┐      ┌───▼──────────────────┐
              │   MIRROR MODE   │      │  CONVERSATION MODE   │
              │                 │      │                       │
              │ • Browser lepas │      │ • Browser lepas       │
              │   kamera        │      │   kamera              │
              │ • Python FER    │      │ • Python FER aktif    │
              │   ambil kamera  │      │ • Prioritas: speaking │
              │ • Robot tiru    │      │   saat TTS aktif      │
              │   emosi user    │      │ • Sela-sela: mirror   │
              │   secara RT     │      │   emosi user          │
              │ • Gaze dari     │      │ • Gaze dari Python    │
              │   Python bbox   │      │   bbox                │
              └────────┬────────┘      └──────────┬────────────┘
                       │                          │
                       │  press D / MQTT mode=default
                       │                          │
                       └────────────┬─────────────┘
                                    ▼
                             (kembali ke DEFAULT)
```

### Tabel Perbandingan Mode

| Aspek | default | mirror | conversation |
|-------|---------|--------|--------------|
| Kamera dipegang | Browser (MediaPipe) | Python (OpenCV) | Python (OpenCV) |
| Source Gaze | MediaPipe bbox | Python bbox → `robot/fer_gaze` | Python bbox → `robot/fer_gaze` |
| Source Ekspresi | Manual / `robot/expression` | `robot/fer_emotion` | `robot/expression` (priority) + `robot/fer_emotion` |
| FER Process | Off/standby | Aktif | Aktif |
| Cocok untuk | Demo / idle / booth | Emotion mirroring demo | Dialog TTS + reaksi emosi |

---

## Alur Data End-to-End

### Default Mode — Siklus Penuh

```
Webcam frame (30fps)
      │
      ▼
MediaPipe Face Detection
      │ boundingBox {xCenter, yCenter}
      ▼
GazeCalculation: rawX = (xCenter-0.5) × -2.0
      │
      ▼
Dead Zone Filter (|x| < 0.04 → 0)
      │
      ▼
EMA Smoothing: smooth = smooth×0.6 + raw×0.4
      │
      ▼                    ┌─────────────────────────┐
getGaze() {x, y} ─────────▶  app.js Tracking Loop  │
                            │                         │
                            │  Check edge threshold   │
                            │  |gaze.x| > 0.65?       │
                            │    YES → hysteresis      │
                            │           hold timer     │
                            │    400ms stabil? → pan  │
                            │                         │
                            │  faceRenderer            │
                            │    .setPupilOffset(x,y)  │
                            └────────────┬────────────┘
                                         │ pupilOffsetX, Y
                                         ▼
                            face-renderer.js drawFace()
                                         │
                                         ├── drawCables()
                                         ├── drawEyeLeft(pupilOX, pupilOY)
                                         │     └── clip ellipse
                                         │         draw gradient
                                         │         draw glint at (cx+pupilOX)
                                         ├── drawEyeRight(pupilOX, pupilOY)
                                         └── drawMouth(state)
                                                    ▼
                                            Canvas 60fps render ✓
```

### Mirror Mode — Siklus Penuh

```
Python FER aktif, kamera dipegang OpenCV
      │
      ▼
cv2.VideoCapture(0) → frame 1280×720
      │
      ▼
HaarCascade detectMultiScale → [x, y, w, h]
      │
      ├── preprocess: crop → resize 112×112 → normalize
      │
      ▼
ONNX InferenceSession.run()
      │ logits [1×5]
      ▼
softmax(logits) → probs [0.1, 0.6, 0.1, 0.1, 0.1]
      │
      ▼
TemporalAveraging.add_prediction(probs)
TemporalAveraging.get_averaged_emotion()
      │ "Happy", conf=0.85
      ▼
confidence ≥ 0.50?
      │ YES
      ▼
EMOTION_TO_EXPRESSION["Happy"] → "happier"
      │
      ▼                                    ┌──────────────────────┐
publish "robot/fer_emotion" ──────────────▶  Mosquitto Broker    │
publish "robot/fer_gaze"    ──────────────▶  port 1883           │
                                            └──────────┬───────────┘
                                                       │ WebSocket 9001
                                            ┌──────────▼───────────┐
                                            │  mqtt-client.js      │
                                            │  Browser subscribe   │
                                            └──────────┬───────────┘
                                                       │
                                            ┌──────────▼───────────┐
                                            │  app.js onMessage    │
                                            │                      │
                                            │  topic fer_emotion:  │
                                            │    faceRenderer      │
                                            │    .setState("happier")
                                            │                      │
                                            │  topic fer_gaze:     │
                                            │    faceRenderer      │
                                            │    .setPupilOffset() │
                                            └──────────────────────┘
```

---

## Struktur File Lengkap

```
IntegrateSpeechExpression/
│
├── README.md                        ← Root entry point (GitHub)
├── DOCS.md                          ← Quick reference dokumentasi
├── JETSON_DEPLOY.md                 ← Panduan deployment (legacy)
├── mosquitto_brone.conf             ← Konfigurasi Mosquitto broker
│
├── index.html                       ← Entry point browser
│   └── Loads (in order):
│       1. js/renderers/fr-transform.js
│       2. js/renderers/fr-blink.js
│       3. js/renderers/fr-cables.js
│       4. js/renderers/fr-eyes.js
│       5. js/renderers/fr-mouths.js
│       6. js/face-renderer.js
│       7. js/face-tracker.js
│       8. js/mqtt-client.js
│       9. js/app.js
│
├── css/
│   └── style.css
│       ├── #faceCanvas          ← Fullscreen canvas
│       ├── #debugPanel          ← Debug overlay
│       ├── #statusIndicator     ← MQTT status badge
│       └── .mode-badge          ← Mode indicator (kanan bawah)
│
├── js/
│   ├── app.js                   ← ExpressionApp class
│   │   ├── constructor()
│   │   ├── initFaceTracker()
│   │   ├── setupEventHandlers()
│   │   ├── setMode(mode)
│   │   ├── startTrackingLoop()
│   │   ├── panHead(direction, trigger)
│   │   ├── handleExpressionMessage(data)
│   │   ├── handleFerEmotion(data)
│   │   ├── handleFerGaze(data)
│   │   └── updateDebugPanel()
│   │
│   ├── face-renderer.js         ← FaceRenderer class
│   │   ├── constructor(canvas)
│   │   ├── setState(state)
│   │   ├── setPupilOffset(x, y)
│   │   ├── startSpeaking()
│   │   ├── stopSpeaking()
│   │   ├── animate(time)
│   │   ├── updateBlink(time)
│   │   ├── updateSpeaking(dt)
│   │   └── drawFace()
│   │
│   ├── face-tracker.js          ← FaceTracker class
│   │   ├── constructor()
│   │   ├── init()
│   │   ├── pause()
│   │   ├── resume()
│   │   ├── getGaze()
│   │   └── _setupMouseFallback()
│   │
│   ├── mqtt-client.js           ← MQTTClient class
│   │   ├── constructor(config)
│   │   ├── connect()
│   │   ├── subscribe(topic)
│   │   ├── publish(topic, payload)
│   │   └── onMessage(callback)
│   │
│   └── renderers/
│       ├── fr-transform.js      ← FRTransform class
│       │   ├── tx(x)            ← translate X
│       │   ├── ty(y)            ← translate Y
│       │   └── ts(size)         ← scale size
│       │
│       ├── fr-blink.js          ← FRBlink class
│       │   ├── update(time)
│       │   ├── forceBlink(nextState)
│       │   └── getProgress()
│       │
│       ├── fr-eyes.js           ← FREyes object
│       │   ├── drawDefault(ctx, t, ox, oy)
│       │   ├── drawSparkle(ctx, t, ox, oy)
│       │   ├── drawCry(ctx, t, ox, oy, animTime)
│       │   └── drawEyelid(ctx, t, progress)
│       │
│       ├── fr-mouths.js         ← FRMouths object
│       │   ├── drawIdle(ctx, t)
│       │   ├── drawSpeaking(ctx, t, phase)
│       │   ├── drawSad(ctx, t)
│       │   ├── drawShock(ctx, t)
│       │   ├── drawCry(ctx, t)
│       │   ├── drawShy(ctx, t)
│       │   └── drawHappier(ctx, t)
│       │
│       └── fr-cables.js         ← FRCables object
│           ├── drawCables(ctx, t)
│           ├── drawBlush(ctx, t)
│           └── drawStar(ctx, t, x, y, size)
│
├── FER-V2/
│   ├── main.py                  ← Stand-alone FER (no MQTT)
│   ├── pub.py                   ← FER Publisher (PyTorch, Intel)
│   ├── main_entry_fer.py        ← Launcher pub + sub
│   ├── models/
│   │   └── fer_model_v1.2_fusion_colab.pth
│   ├── haarcascades/
│   │   └── haarcascade_frontalface_default.xml
│   └── app/
│       └── publisher.py         ← Publisher ONNX (Jetson-optimized)
│
├── jetson-deploy/
│   ├── main-entry.py            ← BroneSystem CLI Launcher
│   ├── config.py                ← BASE_DIR, paths, MQTT config
│   └── publisher_brone.py       ← Patched FER Publisher (mode-aware)
│
├── expression/REFINEMENT/       ← Pygame reference implementations
│   ├── core/
│   │   ├── constants.py         ← Warna, resolusi, posisi mata
│   │   ├── renderer.py          ← Shared draw functions
│   │   ├── blink.py             ← Blink animation
│   │   └── loop.py              ← Pygame main loop
│   └── expressions/
│       ├── happy.py, happier.py, sad.py
│       ├── shock.py, cry.py, shy.py
│       ├── talking.py, load.py
│
├── test_publisher.py            ← Simple MQTT tester
├── test_tts_publisher.py        ← Full-featured interactive tester
│
└── docs/                        ← 📁 Dokumentasi lengkap
    ├── 01-architecture.md       ← File ini
    ├── 02-face-rendering.md
    ├── 03-gaze-tracking.md
    ├── 04-fer-pipeline.md
    ├── 05-mqtt-protocol.md
    ├── 06-head-pan-antishake.md
    ├── 07-tts-conversation.md
    ├── 08-deployment-jetson.md
    └── 09-debugging-testing.md
```

---

## Dependency Loading Order

Urutan load script di `index.html` **kritis** — setiap modul bergantung pada modul di atasnya:

```
index.html
    │
    ├─①─ fr-transform.js    ← harus pertama! Semua renderer pakai FRTransform
    ├─②─ fr-blink.js        ← butuh tidak ada, tapi sebaiknya sebelum renderer
    ├─③─ fr-cables.js       ← pakai FRTransform
    ├─④─ fr-eyes.js         ← pakai FRTransform
    ├─⑤─ fr-mouths.js       ← pakai FRTransform
    ├─⑥─ face-renderer.js   ← pakai semua renderer di atas
    ├─⑦─ face-tracker.js    ← independent (hanya pakai browser API)
    ├─⑧─ mqtt-client.js     ← independent (Paho via CDN)
    └─⑨─ app.js             ← butuh semua modul di atas
```

---

## Mekanisme Switch Kamera

Ini adalah fitur kritis untuk mencegah **Device Busy Error** saat dua proses mencoba akses kamera bersamaan.

```
Trigger: user tekan M (mirror mode)
                │
                ▼
app.js: setMode('mirror')
                │
                ├─ 1. faceTracker.pause()
                │         │
                │         ├── mediaPipeCamera.stop()
                │         ├── videoStream.getTracks()[0].stop()   ← ⚠️ RELEASE KAMERA
                │         └── trackingEnabled = false
                │
                ├─ 2. mqttClient.publish('robot/mode', {mode:'mirror'})
                │                   │
                │                   ▼ (via Mosquitto)
                │         publisher_brone.py._on_message()
                │                   │
                │                   ├── active_mode = 'mirror'
                │                   └── cv2.VideoCapture(0)      ← ⚠️ AMBIL KAMERA
                │
                └─ 3. Subscribe 'robot/fer_emotion', 'robot/fer_gaze'

Trigger: user tekan D (default mode)
                │
                ▼
app.js: setMode('default')
                │
                ├─ 1. mqttClient.publish('robot/mode', {mode:'default'})
                │                   │
                │                   ▼
                │         publisher_brone.py._on_message()
                │                   │
                │                   ├── active_mode = None
                │                   ├── cap.release()            ← ⚠️ RELEASE KAMERA
                │                   └── temporal_avg.reset()
                │
                └─ 2. faceTracker.resume()
                              │
                              ├── getUserMedia() lagi
                              └── mediaPipeCamera.start()        ← ⚠️ AMBIL KAMERA
```

> **Urutan WAJIB**: Browser lepas kamera **SEBELUM** Python mengambil kamera, dan Python lepas kamera **SEBELUM** browser mengambil kembali. Jika urutan terbalik → `Device or resource busy`.

---

← [README](../README.md) | [02 · Face Rendering →](02-face-rendering.md)
