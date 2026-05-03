# 📖 Robot Expression Display — System Documentation

Dokumentasi lengkap arsitektur, logic utama, keyboard controls, MQTT protocol, dan pipeline data untuk proyek **Robot Expression Display**.

---

## Daftar Isi

- [Gambaran Sistem](#gambaran-sistem)
- [Arsitektur File](#arsitektur-file)
- [Keyboard Controls](#keyboard-controls)
- [MQTT Protocol](#mqtt-protocol)
- [Pipeline Data & Logic Utama](#pipeline-data--logic-utama)
- [Face Renderer — Expression States](#face-renderer--expression-states)
- [Face Tracker — Gaze Pipeline](#face-tracker--gaze-pipeline)
- [Head Pan Control — Anti-Shake Logic](#head-pan-control--anti-shake-logic)
- [Pupil Constraint System](#pupil-constraint-system)
- [Konfigurasi & Parameter Tuning](#konfigurasi--parameter-tuning)
- [URL Parameters](#url-parameters)
- [Debug Panel](#debug-panel)
- [Deployment (Jetson)](#deployment-jetson)

---

## Gambaran Sistem

Sistem ini menampilkan **wajah robot animasi** pada HTML5 Canvas yang mampu:
- Menampilkan 7 ekspresi wajah berbeda
- Menggerakkan pupil mengikuti posisi wajah pengguna (via webcam)
- Mengirim perintah head pan ke hardware robot via MQTT
- Sinkronisasi animasi mulut dengan speech event dari MQTT

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER                                  │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐    │
│  │ face-tracker  │──→│    app.js     │──→│  face-renderer   │    │
│  │ (MediaPipe)   │   │ (main logic) │   │  (Canvas draw)   │    │
│  └──────────────┘   └──────┬───────┘   └──────────────────┘    │
│                            │                                    │
│                   ┌────────┴────────┐                           │
│                   │  mqtt-client.js  │                           │
│                   └────────┬────────┘                           │
│                            │                                    │
└────────────────────────────┼────────────────────────────────────┘
                             │ WebSocket (port 9001)
                    ┌────────┴────────┐
                    │ Mosquitto MQTT  │
                    │    Broker       │
                    └────────┬────────┘
                             │ MQTT (port 1883)
                    ┌────────┴────────┐
                    │  Robot Hardware  │
                    │  / Publisher.py  │
                    └─────────────────┘
```

| Komponen | Teknologi |
|----------|-----------|
| Face rendering | HTML5 Canvas (JavaScript) |
| Face tracking | MediaPipe Face Detection (short model) |
| Communication | MQTT via Paho.js (WebSocket) |
| Deployment | NVIDIA Jetson + Chromium Kiosk |
| Fallback input | Mouse/Touch (jika kamera ditolak) |

---

## Arsitektur File

```
IntegrateSpeechExpression/
├── index.html              # Entry point — memuat semua script & UI
├── css/
│   └── style.css           # Styling: debug panel, status indicator
├── js/
│   ├── app.js              # Main logic: event handling, head pan, tracking loop
│   ├── face-renderer.js    # Canvas rendering: mata, mulut, ekspresi, blink
│   ├── face-tracker.js     # MediaPipe face detection + gaze smoothing
│   └── mqtt-client.js      # MQTT WebSocket client (Paho wrapper)
├── expression/
│   └── REFINEMENT/         # Python/Pygame reference implementations per ekspresi
│       ├── rcry.py
│       ├── rhappier.py
│       ├── rhappy.py
│       ├── rload.py
│       ├── rsad.py
│       ├── rshock.py
│       ├── rshy.py
│       └── rtalkingState.py
├── test_publisher.py       # Python MQTT test publisher (CLI)
├── JETSON_DEPLOY.md        # Panduan deployment ke Jetson
├── TENSORFLOWJS_DOCS.md    # Dokumentasi TF.js / face tracking
└── README_RESEARCH.md      # Topik riset potensial
```

---

## Keyboard Controls

Semua keyboard shortcut didefinisikan di `app.js` → `setupEventHandlers()`:

### Expression Controls

| Key | Aksi | Detail |
|-----|------|--------|
| `s` | **Speaking** | Mulut beranimasi buka-tutup selama 3 detik |
| `i` atau `0` | **Idle** | Kembali ke wajah default (senyum) |
| `1` | **Sad** | Ekspresi sedih — mulut melengkung ke bawah |
| `2` | **Shock** | Ekspresi terkejut — mulut oval besar |
| `3` | **Cry** | Ekspresi menangis — air mata + wave effect pada mata |
| `4` | **Shy** | Ekspresi malu — blush + mata sparkle + mulut ω |
| `5` | **Happier** | Ekspresi sangat senang — blush + sparkle + senyum lebar |

### System Controls

| Key | Aksi | Detail |
|-----|------|--------|
| `d` | **Toggle Debug Panel** | Menampilkan/menyembunyikan debug overlay di pojok kiri atas |
| `t` | **Toggle Face Tracking** | ON/OFF deteksi wajah via webcam |
| `r` | **Reset Head Angle** | Mengembalikan sudut pan kepala ke 0° (tengah) |
| `←` Arrow Left | **Manual Head Pan Left** | Putar kepala ke kiri sebesar `HEAD_PAN_STEP` (15°) |
| `→` Arrow Right | **Manual Head Pan Right** | Putar kepala ke kanan sebesar `HEAD_PAN_STEP` (15°) |

### Alur Keyboard → Rendering

```
KeyPress 's'
    │
    ▼
app.js: handleExpressionMessage({ expression: 'speaking', duration: 3 })
    │
    ▼
app.js: startSpeaking(3)
    │
    ├── faceRenderer.startSpeaking()     → state = 'speaking'
    │                                       speakingPhase mulai bergerak
    │
    └── setTimeout(stopSpeaking, 3000)   → setelah 3 detik, kembali ke idle
```

```
KeyPress '3'
    │
    ▼
app.js: handleExpressionMessage({ expression: 'cry', duration: 0 })
    │
    ▼
app.js: stopSpeaking()  → hentikan timer speaking jika ada
    │
    ▼
faceRenderer.setState('cry')
    │
    ▼
Trigger blink → saat mata tertutup penuh, swap state ke 'cry'
    │
    ▼
drawFace() sekarang memanggil:
    ├── drawPurpleEyeWithWave()    → mata dengan water wave effect
    ├── drawCartoonStream()         → aliran air mata
    └── drawCryMouth()              → mulut sedih terbalik (tanpa lidah)
```

---

## MQTT Protocol

### Topics

| Topic | Arah | QoS | Deskripsi |
|-------|------|-----|-----------|
| `robot/expression` | **Subscribe** | 0/1 | Menerima perintah ekspresi dari publisher |
| `robot/head_control` | **Publish** | 0 | Mengirim perintah pan kepala ke robot |
| `robot/tracking_state` | **Publish** | 0 | Telemetri tracking (debug, ~6.7 Hz) |

### Payload: `robot/expression` (Incoming)

```json
{
    "expression": "speaking",   // "idle"|"speaking"|"sad"|"shock"|"cry"|"shy"|"happier"
    "duration": 3.0             // detik (hanya untuk "speaking", 0 untuk lainnya)
}
```

### Payload: `robot/head_control` (Outgoing)

```json
{
    "pan_deg": 15.0,            // sudut pan saat ini (-45 s/d +45)
    "tilt_deg": 0,              // reserved untuk pengembangan
    "pan_norm": 0.333,          // pan dinormalisasi (-1.0 s/d +1.0)
    "trigger": "pupil_edge",    // "pupil_edge"|"manual_key"|"reset"
    "at_limit": false,          // true jika sudah di batas ±45°
    "timestamp_ms": 1712678400000
}
```

### Payload: `robot/tracking_state` (Outgoing, Telemetry)

```json
{
    "face_detected": true,
    "raw_gaze_x": 0.342,        // -1.0 s/d +1.0
    "raw_gaze_y": -0.128,
    "head_pan_deg": 15.0,
    "head_pan_norm": 0.333,
    "pupil_at_edge": false,
    "edge_hold_pct": 0,         // 0-100, progress hysteresis hold
    "tracking_enabled": true,
    "timestamp_ms": 1712678400000
}
```

### Mengirim Perintah via Python

```python
import paho.mqtt.client as mqtt
import json

client = mqtt.Client()
client.connect("localhost", 1883)

# Robot mulai berbicara selama 5 detik
client.publish("robot/expression", json.dumps({
    "expression": "speaking",
    "duration": 5.0
}))

# Robot menampilkan ekspresi sedih
client.publish("robot/expression", json.dumps({
    "expression": "sad",
    "duration": 0
}))
```

---

## Pipeline Data & Logic Utama

### Boot Sequence

```
DOMContentLoaded
    │
    ▼
new ExpressionApp()
    │
    ├── new FaceRenderer(canvas)    → mulai animation loop (60fps)
    │       └── animate() → requestAnimationFrame loop
    │           ├── updateBlink()
    │           ├── updateSpeaking()
    │           ├── clear()
    │           └── drawFace()
    │
    ├── new MQTTClient(config)
    │       └── connect() → WebSocket ke Mosquitto port 9001
    │           └── subscribe('robot/expression')
    │
    ├── setupEventHandlers()        → keyboard listeners + MQTT callbacks
    │
    ├── initFaceTracker()           → async
    │       ├── getUserMedia(640×480)
    │       ├── new FaceDetection({ model: 'short' })
    │       ├── camera.start()      → MediaPipe Camera utility
    │       └── startTrackingLoop() → requestAnimationFrame loop
    │
    └── showStatusBriefly()         → flash MQTT status 3 detik
```

### Main Loop (60fps)

Ada **dua loop** yang berjalan paralel:

| Loop | Frekuensi | File | Tugas |
|------|-----------|------|-------|
| **Render Loop** | 60 fps | face-renderer.js | Menggambar wajah, mata, mulut, blink, ekspresi |
| **Tracking Loop** | 60 fps | app.js | Membaca gaze dari tracker, head pan logic, MQTT telemetry |
| **Detection** | ~30 fps | face-tracker.js | MediaPipe inferensi (asynchronous, dikelola Camera utility) |

```
┌─── Render Loop (face-renderer.js) ────────────────────────────┐
│                                                                │
│  animate(currentTime):                                         │
│    1. deltaTime = (currentTime - lastTime) / 1000              │
│    2. updateBlink(currentTime)     → auto blink setiap 2-6s    │
│    3. updateSpeaking(deltaTime)    → oscillate mouth jika state │
│                                      = 'speaking'              │
│    4. animationTime += deltaTime   → global time untuk wave     │
│    5. clear()                      → fill background           │
│    6. drawFace()                   → gambar semua komponen      │
│    7. requestAnimationFrame(animate)                            │
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌─── Tracking Loop (app.js) ────────────────────────────────────┐
│                                                                │
│  loop():                                                       │
│    1. gaze = faceTracker.getGaze()     → { x, y } smoothed     │
│    2. Check edge threshold             → |gaze.x| > 0.65?      │
│    3. Hysteresis hold timer            → held ≥ 400ms?          │
│    4. Rate limit check                 → last cmd > 600ms ago?  │
│    5. If all pass → panHead()          → MQTT publish           │
│    6. faceRenderer.setPupilOffset(x, y)                         │
│    7. updateHeadControlDebug()         → update debug UI        │
│    8. publishTrackingState() every 150ms                        │
│    9. requestAnimationFrame(loop)                               │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Face Renderer — Expression States

### State Machine

```
                    ┌──────────────┐
            ┌──────│    idle       │◄──────┐
            │      │  (senyum)    │       │
            │      └──────────────┘       │
            │        ▲   ▲   ▲            │
     ┌──────┘    ┌───┘   │   └───┐        │
     ▼           │       │       │        │
┌────────┐  ┌────────┐ ┌─────┐ ┌──────┐ ┌───────┐
│speaking│  │  sad   │ │shock│ │ cry  │ │  shy  │
│(mulut  │  │(mulut  │ │(O)  │ │(wave │ │(blush │
│ oscil) │  │ frown) │ │     │ │+tear)│ │+ω lip)│
└────────┘  └────────┘ └─────┘ └──────┘ └───────┘
     │                                    ▲
     │                              ┌─────┘
     │                         ┌────────┐
     └─── (timer habis) ──────│happier │
                               │(blush+ │
                               │sparkle)│
                               └────────┘
```

**Transisi antar state** terjadi melalui mekanisme **blink-swap**: saat ekspresi berubah, mata akan menutup (blink) terlebih dahulu, state di-swap saat mata tertutup penuh, lalu mata membuka di ekspresi baru. Ini memberikan transisi yang natural.

### Komponen Visual per State

| State | Mata | Mulut | Efek Tambahan |
|-------|------|-------|---------------|
| `idle` | Gradient (ungu→hitam) + highlight | Senyum kurva + lidah | — |
| `speaking` | Sama seperti idle | Oval buka-tutup + lidah | Animasi oscillation |
| `sad` | Sama seperti idle | Frown (lengkung ke atas terbalik) | — |
| `shock` | Sama seperti idle | Oval besar + lidah | Mulut berubah saat blink |
| `cry` | Purple + water wave | Frown besar (tanpa lidah) | Air mata stream + drops |
| `shy` | Gradient + sparkle stars | Dua half-circle (ω shape) | Blush (pipi merah) |
| `happier` | Gradient + sparkle stars | Senyum kurva + lidah | Blush (pipi merah) |

### Blink System

```
Timeline:
  idle ──────────── closing ──── [SWAP STATE] ──── opening ──── idle
                   progress 0→1                   progress 1→0
                   speed: 0.08                     speed: 0.08
                   (0.20 jika swap)                (0.20 jika swap)

Random delay antara blink: 2000 – 6000 ms
```

- `blinkProgress = 0` → mata terbuka penuh
- `blinkProgress = 1` → mata tertutup penuh
- Saat `blinkProgress = 1` dan ada `nextState` → state di-swap
- Kelopak mata digambar sebagai rectangle berwarna background + garis hitam

---

## Face Tracker — Gaze Pipeline

### Detection → Gaze Flow

```
Webcam 640×480
    │
    ▼
MediaPipe Face Detection (model: 'short')
    │
    ▼ results.detections[0].boundingBox
    │   { xCenter, yCenter, width, height }  ← normalized 0..1
    │
    ▼ Gaze Calculation
    rawGazeX = (xCenter - 0.5) × -2.0       ← mirror + normalize ke [-1, 1]
    rawGazeY = (yCenter - 0.5) × 2.0        ← normalize ke [-1, 1]
    │
    ▼ Dead Zone Filter
    if |rawX| < 0.04 → rawX = 0             ← ignore micro-movement
    │
    ▼ Clamp
    gazeX = clamp(rawX, -1, 1)
    │
    ▼ Exponential Moving Average (EMA)
    smoothGazeX = smooth × 0.60 + raw × 0.40
    │
    ▼ Output
    getGaze() → { x: smoothGazeX, y: smoothGazeY }
```

### Fallback (Kamera Ditolak)

Jika `getUserMedia()` gagal (user menolak izin kamera), sistem otomatis beralih ke **mouse/touch fallback**:

```
Mouse position → normalize to [-1, 1] → lighter smoothing (factor 0.5) → getGaze()
```

### No-Face Behavior

Saat tidak ada wajah terdeteksi, gaze perlahan kembali ke tengah:

```
gazeX *= 0.92    // decay 8% per frame
gazeY *= 0.92
if |gazeX| < 0.01 → gazeX = 0   // snap to zero
```

---

## Head Pan Control — Anti-Shake Logic

### Mengapa Ada Hysteresis?

Tanpa hysteresis, gaze yang berfluktuasi di sekitar threshold akan menyebabkan head pan berulang-ulang (jittering). Sistem menggunakan **dua mekanisme anti-shake**:

### Mekanisme 1: Hysteresis Hold (400ms)

Gaze harus **tetap** di luar threshold selama minimal 400ms sebelum head pan di-trigger.

```
gaze.x = 0.72 (> threshold 0.65)
    │
    ▼ edgeHoldStart = Date.now()
    │
    .... 100ms → holdDuration = 100ms < 400ms → WAIT
    .... 200ms → holdDuration = 200ms < 400ms → WAIT
    .... 300ms → holdDuration = 300ms < 400ms → WAIT
    .... 400ms → holdDuration = 400ms ≥ 400ms → ✅ FIRE!
    │
    ▼ panHead(direction × 15°, 'pupil_edge')
    
TETAPI jika gaze kembali ke < 0.65 sebelum 400ms:
    → edgeHoldStart = null (RESET, tidak jadi fire)
```

### Mekanisme 2: Rate Limiting (600ms)

Minimal 600ms antara dua head pan command berturut-turut.

```
Command fired at t=0
    │
    .... t=300ms → gaze at edge lagi → holdDuration ≥ 400ms?
    │              YES, tapi 300ms < 600ms rate limit → BLOCKED
    │
    .... t=600ms → rate limit terpenuhi → cek hold lagi → FIRE
```

### Head Pan Range

```
HEAD_MIN_ANGLE = -45°  (kiri maksimum)
HEAD_MAX_ANGLE = +45°  (kanan maksimum)
HEAD_PAN_STEP  =  15°  (per trigger event)

Total steps kiri ke kanan: 6 langkah (-45 → -30 → -15 → 0 → 15 → 30 → 45)
```

---

## Pupil Constraint System

Tiga lapis mekanisme mencegah pupil keluar dari bola mata:

### Lapis 1 — Input Clamping (`face-tracker.js`)

```javascript
gazeX = Math.max(-1, Math.min(1, rawX));   // tidak pernah di luar [-1, 1]
gazeY = Math.max(-1, Math.min(1, rawY));
```

### Lapis 2 — Pixel Shift Limit (`face-renderer.js`)

```javascript
MAX_PUPIL_SHIFT_X = 20;   // pupil maksimum bergeser ±20px dari pusat mata
MAX_PUPIL_SHIFT_Y = 22;   // pupil maksimum bergeser ±22px dari pusat mata

// Konversi: [-1..1] × 20 = [-20..20] pixel (referensi 800×600)
shiftX = pupilOffsetX * MAX_PUPIL_SHIFT_X;
shiftY = pupilOffsetY * MAX_PUPIL_SHIFT_Y;
```

### Lapis 3 — Canvas Clip (Visual Safety Net)

```javascript
// Eye ellipse didefinisikan sebagai clip region
ctx.ellipse(eyeCenterX, eyeCenterY, eyeWidth/2, eyeHeight/2, ...);
ctx.clip();   // ← semua drawing setelah baris ini terpotong di batas ellipse

// Pupil highlight digambar di dalam clip → otomatis terpotong jika keluar
ctx.arc(glintX, glintY, 22, 0, Math.PI * 2);
ctx.fill();

ctx.restore();  // ← release clip
```

**Hasil:** Bahkan jika secara matematis pupil keluar batas, secara visual tetap terpotong oleh clip region ellipse mata.

---

## Konfigurasi & Parameter Tuning

### face-tracker.js

| Parameter | Default | Range yang Dianjurkan | Efek |
|-----------|---------|----------------------|------|
| `smoothingFactor` | `0.60` | 0.3 – 0.8 | Lebih tinggi = gerakan lebih halus tapi lambat merespons |
| `deadZone` | `0.04` | 0.02 – 0.10 | Lebih tinggi = area "diam" di tengah lebih besar |
| `minDetectionConfidence` | `0.5` | 0.3 – 0.8 | Lebih rendah = lebih sensitif tapi lebih banyak false positive |

### face-renderer.js

| Parameter | Default | Efek |
|-----------|---------|------|
| `MAX_PUPIL_SHIFT_X` | `20` | Batas horizontal gerakan pupil dalam pixel (ref 800×600) |
| `MAX_PUPIL_SHIFT_Y` | `22` | Batas vertikal gerakan pupil dalam pixel |
| `speakingSpeed` | `4` | Kecepatan oscillation mulut saat speaking (osc/detik) |

### app.js

| Parameter | Default | Efek |
|-----------|---------|------|
| `HEAD_MAX_ANGLE` | `45°` | Batas rotasi kepala robot |
| `HEAD_PAN_STEP` | `15°` | Derajat rotasi per trigger event |
| `PUPIL_EDGE_THRESHOLD` | `0.65` | Gaze threshold sebelum head pan (0–1) |
| `EDGE_HOLD_REQUIRED` | `400ms` | Durasi gaze harus "stay" di edge sebelum pan trigger |
| `HEAD_COMMAND_INTERVAL` | `600ms` | Minimum gap antar perintah head pan |
| `TELEMETRY_INTERVAL` | `150ms` | Rate telemetry publish (~6.7 Hz) |

### mqtt-client.js

| Parameter | Default | Efek |
|-----------|---------|------|
| `host` | `localhost` | Alamat MQTT broker |
| `port` | `9001` | Port WebSocket MQTT |
| `topic` | `robot/expression` | Topic subscribe utama |
| `reconnectInterval` | `3000ms` | Interval reconnect saat terputus |

---

## URL Parameters

Konfigurasi MQTT dapat di-override melalui URL query parameters:

```
http://localhost:8080?mqtt_host=192.168.1.100&mqtt_port=9001&mqtt_topic=custom/topic
```

| Parameter | Default | Deskripsi |
|-----------|---------|-----------|
| `mqtt_host` | `localhost` | Host MQTT broker |
| `mqtt_port` | `9001` | Port WebSocket MQTT |
| `mqtt_topic` | `robot/expression` | Topic untuk subscribe |

---

## Debug Panel

Tekan **`D`** untuk menampilkan/menyembunyikan debug panel di pojok kiri atas.

### Konten Debug Panel

| Section | Informasi |
|---------|-----------|
| **Face Detection Status** | Dot berwarna (hijau=detected, kuning=searching, biru=mouse mode, merah=error) + teks status |
| **Mini Webcam Preview** | Feed kamera kecil + bbox overlay hijau di wajah yang terdeteksi |
| **Head Control Panel** | Pan angle bar (visual), raw gaze XY, compensated gaze, edge hold progress bar, MQTT payload preview |

### Status Dot Colors

| Warna | Status |
|-------|--------|
| 🟢 Hijau | Wajah terdeteksi |
| 🟡 Kuning | Mencari wajah... |
| 🔵 Biru | Mode mouse (kamera ditolak) |
| 🔴 Merah | Error |
| ⚪ Abu-abu | Inisialisasi |

---

## Deployment (Jetson)

Lihat [JETSON_DEPLOY.md](JETSON_DEPLOY.md) untuk panduan lengkap. Ringkasan:

1. Install Mosquitto MQTT Broker dengan WebSocket support (port 9001)
2. Serve file via Python HTTP server atau Nginx
3. Buka Chromium di kiosk mode: `chromium-browser --kiosk http://localhost:8080`
4. Systemd service untuk auto-start

### Test Cepat

```bash
# Terminal 1: Subscribe untuk monitoring
mosquitto_sub -t "robot/#" -v

# Terminal 2: Kirim ekspresi
mosquitto_pub -t "robot/expression" -m '{"expression":"speaking","duration":3}'

# Terminal 3: Test publisher interaktif
python3 test_publisher.py --loop
```

---

*Dokumentasi ini mencakup seluruh logic utama proyek Robot Expression Display v2.*
*Terakhir diperbarui: April 2026*
