# 05 · MQTT Protocol — Topics, Payload & Routing

← [04 · FER Pipeline](04-fer-pipeline.md) | [06 · Head Pan & Anti-Shake →](06-head-pan-antishake.md)

---

## Daftar Isi

- [Infrastruktur Broker](#infrastruktur-broker)
- [Semua Topic & Arah Aliran](#semua-topic--arah-aliran)
- [Schema Payload Lengkap](#schema-payload-lengkap)
- [Message Routing di app.js](#message-routing-di-appjs)
- [Contoh Publisher Python](#contoh-publisher-python)
- [Konfigurasi mosquitto_brone.conf](#konfigurasi-mosquitto_broneconf)

---

## Infrastruktur Broker

```
  ┌────────────────────────────────────────────────────────────┐
  │                   Mosquitto MQTT Broker                    │
  │                                                            │
  │  ┌─────────────────────┐    ┌────────────────────────┐    │
  │  │  Listener Port 1883  │    │  Listener Port 9001    │    │
  │  │  Protocol: MQTT TCP  │    │  Protocol: WebSocket   │    │
  │  │  allow_anonymous:true│    │  allow_anonymous: true │    │
  │  └──────────┬──────────┘    └───────────┬────────────┘    │
  │             │                           │                  │
  └─────────────┼───────────────────────────┼──────────────────┘
                │                           │
        ┌───────┴──────┐           ┌────────┴──────────┐
        │ Python Client │           │ Browser (Paho.js) │
        │ paho-mqtt     │           │ WebSocket         │
        │               │           │                   │
        │ publisher.py  │           │ mqtt-client.js    │
        │ main-entry.py │           │ app.js            │
        │ test_*.py     │           │                   │
        └───────────────┘           └───────────────────┘
```

### Konfigurasi mosquitto_brone.conf

```ini
# Mosquitto Configuration for BRONE
# Jalankan: mosquitto -v -c mosquitto_brone.conf

# === Listener 1: Native MQTT (untuk Python publisher) ===
listener 1883
protocol mqtt
allow_anonymous true

# === Listener 2: WebSocket (untuk Browser display) ===
listener 9001
protocol websockets
allow_anonymous true
```

**Cara menjalankan:**
```bash
# Windows
& "C:\Program Files\mosquitto\mosquitto.exe" -v -c mosquitto_brone.conf

# Linux/Jetson
mosquitto -v -c mosquitto_brone.conf
# atau sebagai service:
sudo systemctl start mosquitto
```

---

## Semua Topic & Arah Aliran

```
┌───────────────────────────────────────────────────────────────────────┐
│                    MQTT Topic Map                                      │
│                                                                        │
│  PUBLISHER                    TOPIC              SUBSCRIBER           │
│  ─────────                    ─────              ──────────           │
│                                                                        │
│  test_*.py         ──────▶  robot/expression  ──────▶  app.js        │
│  main-entry.py     ──────▶  robot/expression  ──────▶  app.js        │
│  TTS system        ──────▶  robot/expression  ──────▶  app.js        │
│                                                                        │
│  publisher_brone   ──────▶  robot/fer_emotion ──────▶  app.js        │
│  pub.py            ──────▶  robot/fer_emotion ──────▶  app.js        │
│                                                                        │
│  publisher_brone   ──────▶  robot/fer_gaze    ──────▶  app.js        │
│                                                                        │
│  main-entry.py     ──────▶  robot/mode        ──────▶  app.js        │
│  app.js (keyboard) ──────▶  robot/mode        ──────▶  publisher     │
│                                                                        │
│  app.js            ──────▶  robot/head_control──────▶  Robot HW      │
│                                                                        │
│  app.js            ──────▶  robot/tracking_state ────▶  Debug tools  │
│                                                                        │
└───────────────────────────────────────────────────────────────────────┘

Legenda arah:
  ──▶  publish ke topic
  ◀──  subscribe dari topic
```

### Ringkasan Topic

| Topic | QoS | Retain | Arah | Frekuensi |
|-------|-----|--------|------|-----------|
| `robot/expression` | 1 | No | → Browser | On-demand |
| `robot/fer_emotion` | 0 | No | → Browser | ~5-10 Hz |
| `robot/fer_gaze` | 0 | No | → Browser | ~30 Hz |
| `robot/mode` | 1 | Yes | Bidirectional | On-demand |
| `robot/head_control` | 0 | No | → Hardware | On-demand |
| `robot/tracking_state` | 0 | No | → Debug | ~6.7 Hz |

---

## Schema Payload Lengkap

### 1. `robot/expression` — Perintah Ekspresi

```json
{
    "expression": "speaking",
    "duration": 3.0
}
```

| Field | Type | Values | Keterangan |
|-------|------|--------|------------|
| `expression` | string | `"idle"`, `"speaking"`, `"sad"`, `"shock"`, `"cry"`, `"shy"`, `"happier"` | State visual yang akan ditampilkan |
| `duration` | float | `0.0` – `∞` | Durasi dalam detik. Hanya relevan untuk `"speaking"`. Nilai `0` = permanent |

**Contoh penggunaan:**
```json
// Robot berbicara 5 detik
{"expression": "speaking", "duration": 5.0}

// Robot sedih (permanent hingga perintah berikutnya)
{"expression": "sad", "duration": 0}

// Robot kembali idle
{"expression": "idle", "duration": 0}
```

---

### 2. `robot/fer_emotion` — Data Emosi dari FER

```json
{
    "timestamp": 1712678400.123,
    "emotion": "Happy",
    "expression": "happier",
    "confidence": 0.89
}
```

| Field | Type | Values | Keterangan |
|-------|------|--------|------------|
| `timestamp` | float | Unix timestamp | Waktu prediksi |
| `emotion` | string | `"Happy"`, `"Neutral"`, `"Sad"`, `"Shocked"`, `"Upset"` | Label emosi dari model ML |
| `expression` | string | (sama dengan robot/expression) | Hasil mapping emotion→expression |
| `confidence` | float | 0.0 – 1.0 | Confidence setelah temporal averaging |

**Catatan:** Browser hanya menggunakan field `expression`. Field `emotion` dan `confidence` untuk logging/debug.

---

### 3. `robot/fer_gaze` — Gaze dari Python

```json
{
    "gaze_x": 0.342,
    "gaze_y": -0.128,
    "face_detected": true,
    "timestamp": 1712678400.456
}
```

```json
{
    "face_detected": false,
    "timestamp": 1712678400.789
}
```

| Field | Type | Range | Keterangan |
|-------|------|-------|------------|
| `gaze_x` | float | -1.0 – +1.0 | Horizontal gaze. Negatif=kiri, positif=kanan |
| `gaze_y` | float | -1.0 – +1.0 | Vertikal gaze. Negatif=atas, positif=bawah |
| `face_detected` | bool | — | Apakah wajah terdeteksi di frame ini |
| `timestamp` | float | Unix timestamp | Waktu estimasi |

---

### 4. `robot/mode` — Switch Mode Sistem

```json
{
    "mode": "mirror",
    "timestamp_ms": 1712678400000
}
```

| Field | Type | Values | Keterangan |
|-------|------|--------|------------|
| `mode` | string | `"default"`, `"mirror"`, `"conversation"` | Mode operasi target |
| `timestamp_ms` | int | Unix ms | Untuk ordering/dedup |

---

### 5. `robot/head_control` — Perintah Servo

```json
{
    "pan_deg": 15.0,
    "tilt_deg": 0,
    "pan_norm": 0.333,
    "trigger": "pupil_edge",
    "at_limit": false,
    "timestamp_ms": 1712678400000
}
```

| Field | Type | Range | Keterangan |
|-------|------|-------|------------|
| `pan_deg` | float | -45.0 – +45.0 | Target angle absolut. 0=center |
| `tilt_deg` | int | 0 | Reserved (belum diimplementasi) |
| `pan_norm` | float | -1.0 – +1.0 | `pan_deg / 45` |
| `trigger` | string | `"pupil_edge"`, `"manual_key"`, `"reset"` | Pemicu perintah |
| `at_limit` | bool | — | True jika sudah di batas ±45° |
| `timestamp_ms` | int | — | Timestamp |

---

### 6. `robot/tracking_state` — Telemetri (Debug)

```json
{
    "face_detected": true,
    "raw_gaze_x": 0.342,
    "raw_gaze_y": -0.128,
    "smooth_gaze_x": 0.298,
    "smooth_gaze_y": -0.091,
    "head_pan_deg": 15.0,
    "head_pan_norm": 0.333,
    "pupil_at_edge": false,
    "edge_hold_pct": 0,
    "tracking_enabled": true,
    "mode": "default",
    "timestamp_ms": 1712678400000
}
```

---

## Message Routing di app.js

```
mqtt-client.js: onMessage(topic, payload)
        │
        ▼
app.js: handleMessage(topic, data):
        │
        ├── topic === 'robot/expression'
        │       │
        │       └── handleExpressionMessage(data)
        │               │
        │               ├── data.expression === 'speaking':
        │               │       startSpeaking(data.duration)
        │               │
        │               ├── data.expression === 'idle':
        │               │       stopSpeaking()
        │               │       faceRenderer.setState('idle')
        │               │
        │               └── otherwise:
        │                       stopSpeaking()
        │                       faceRenderer.setState(data.expression)
        │
        ├── topic === 'robot/fer_emotion'
        │       │
        │       └── handleFerEmotion(data)
        │               │
        │               ├── Cek mode saat ini === 'mirror' atau 'conversation'
        │               │     (jika default → ignore)
        │               │
        │               ├── data.confidence < 0.50 → ignore
        │               │
        │               └── faceRenderer.setState(data.expression)
        │
        ├── topic === 'robot/fer_gaze'
        │       │
        │       └── handleFerGaze(data)
        │               │
        │               ├── data.face_detected === false:
        │               │       faceRenderer.setPupilOffset(0, 0)
        │               │
        │               └── data.face_detected === true:
        │                       faceRenderer.setPupilOffset(
        │                           data.gaze_x, data.gaze_y
        │                       )
        │
        └── topic === 'robot/mode'
                │
                └── setMode(data.mode)
                        │
                        ├── 'default' → faceTracker.resume()
                        ├── 'mirror'  → faceTracker.pause()
                        │               subscribe fer_emotion, fer_gaze
                        └── 'conversation' → faceTracker.pause()
                                             subscribe fer_emotion, fer_gaze
```

---

## Contoh Publisher Python

### Publisher Sederhana

```python
import paho.mqtt.client as mqtt
import json, time

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("localhost", 1883)
client.loop_start()
time.sleep(0.5)

# Kirim speaking 5 detik
client.publish("robot/expression", json.dumps({
    "expression": "speaking",
    "duration": 5.0
}))

# Kirim emosi (simulasi FER)
client.publish("robot/fer_emotion", json.dumps({
    "timestamp": time.time(),
    "emotion": "Happy",
    "expression": "happier",
    "confidence": 0.85
}))

# Switch mode
client.publish("robot/mode", json.dumps({
    "mode": "mirror",
    "timestamp_ms": int(time.time() * 1000)
}))

client.loop_stop()
client.disconnect()
```

### Interactive Publisher (test_tts_publisher.py)

```bash
python3 test_tts_publisher.py

# Commands:
  speak 3        → speaking animation 3 detik
  fer happy      → simulasi FER emosi Happy
  fer sad        → simulasi FER emosi Sad
  expr shy       → ekspresi shy langsung
  mode mirror    → switch ke mirror mode
  mode default   → kembali ke default
  idle           → kembali ke idle
  help           → tampilkan bantuan
  quit           → keluar
```

### CLI Monitoring

```bash
# Monitor semua topic sekaligus
mosquitto_sub -t "robot/#" -v

# Monitor satu topic
mosquitto_sub -t "robot/head_control" -v

# Filter JSON dan pretty print
mosquitto_sub -t "robot/fer_emotion" | python3 -c "
import sys, json
for line in sys.stdin:
    try: print(json.dumps(json.loads(line), indent=2))
    except: print(line)
"
```

---

← [04 · FER Pipeline](04-fer-pipeline.md) | [06 · Head Pan & Anti-Shake →](06-head-pan-antishake.md)
