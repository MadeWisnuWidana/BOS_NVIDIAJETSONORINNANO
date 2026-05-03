# 🤖 BRONE — Robot Expression Display

Sistem tampilan wajah robot interaktif berbasis **HTML5 Canvas + MQTT + FER AI**, dirancang untuk berjalan di **NVIDIA Jetson** sebagai kepala robot.

```
  ┌──────────────────────────────────────────────────────────┐
  │   ◉─────────────────────────────────────────────────◉   │
  │   │                                                 │   │
  │   │    ╭───────╮          ╭───────╮                 │   │
  │   │    │       │          │       │                 │   │
  │   │    │  ◕   │          │  ◕   │                 │   │
  │   │    │       │          │       │                 │   │
  │   │    ╰───────╯          ╰───────╯                 │   │
  │   │                                                 │   │
  │   │             ╭─────────────╮                     │   │
  │   │             │   ~~^~^~~   │                     │   │
  │   │             ╰─────────────╯                     │   │
  │   │                                                 │   │
  │   ◉─────────────────────────────────────────────────◉   │
  └──────────────────────────────────────────────────────────┘
                  BRONE — Expression Display
```

## Fitur Utama

- 🎭 **7 Ekspresi Wajah**: idle, speaking, sad, shock, cry, shy, happier
- 👁️ **Real-time Gaze Tracking** via MediaPipe (pupil mengikuti wajah pengguna)
- 🤖 **Head Pan Control** ke servo leher robot via MQTT (dengan anti-shake hysteresis)
- 🧠 **Facial Emotion Recognition** (FER-V2): AI mendeteksi emosi dan robot menirunya
- 📡 **MQTT Integration**: WebSocket (browser) + Native MQTT (Python)
- 🖥️ **Kiosk-ready** untuk NVIDIA Jetson + Chromium

---

## Quick Start

```bash
# 1. Start MQTT Broker
mosquitto -v -c mosquitto_brone.conf

# 2. Serve display
python3 -m http.server 8080

# 3. Buka browser
chromium-browser http://localhost:8080

# 4. Test ekspresi (terminal baru)
python3 test_tts_publisher.py
```

---

## Dokumentasi Lengkap

> 📁 Semua dokumen teknis tersimpan di folder [`docs/`](docs/)

| Dokumen | Topik |
|---------|-------|
| [**01 · Arsitektur Sistem**](docs/01-architecture.md) | Topologi, mode operasi, alur data end-to-end, struktur file |
| [**02 · Face Rendering**](docs/02-face-rendering.md) | Canvas drawing, semua fungsi ekspresi, blink-swap, koordinat transform |
| [**03 · Gaze Tracking**](docs/03-gaze-tracking.md) | MediaPipe pipeline, EMA smoothing, fallback mouse, pupil constraint |
| [**04 · FER Pipeline**](docs/04-fer-pipeline.md) | Model ResNet34/ONNX, temporal averaging, emotion→expression mapping |
| [**05 · MQTT Protocol**](docs/05-mqtt-protocol.md) | Semua topic, payload schema lengkap, contoh publisher Python |
| [**06 · Head Pan & Anti-Shake**](docs/06-head-pan-antishake.md) | Hysteresis hold, rate limiting, servo angle, algoritma step-by-step |
| [**07 · TTS & Conversation Mode**](docs/07-tts-conversation.md) | Speaking animation, mode conversation, integrasi TTS publisher |
| [**08 · Deployment Jetson**](docs/08-deployment-jetson.md) | Instalasi, Mosquitto config, kiosk mode, systemd, troubleshooting |
| [**09 · Debugging & Testing**](docs/09-debugging-testing.md) | Debug panel, test_publisher, mosquitto_sub CLI, keyboard shortcuts |

---

## Struktur Proyek

```
IntegrateSpeechExpression/
├── README.md                    ← Anda di sini
├── DOCS.md                      ← Ringkasan teknis (quick reference)
├── index.html                   ← Entry point browser
├── css/style.css
├── js/
│   ├── app.js                   ← Orchestrator utama
│   ├── face-renderer.js         ← Canvas renderer
│   ├── face-tracker.js          ← MediaPipe gaze tracking
│   ├── mqtt-client.js           ← MQTT WebSocket client
│   └── renderers/
│       ├── fr-transform.js      ← Koordinat transform
│       ├── fr-blink.js          ← Blink state machine
│       ├── fr-eyes.js           ← Gambar mata & efek
│       ├── fr-mouths.js         ← Gambar mulut semua ekspresi
│       └── fr-cables.js         ← Kabel, blush, bintang
├── FER-V2/                      ← AI Emotion Recognition
│   ├── pub.py                   ← Publisher PyTorch (Intel/laptop)
│   ├── main_entry_fer.py        ← Launcher FER system
│   └── app/publisher.py         ← Publisher ONNX (Jetson)
├── jetson-deploy/
│   ├── main-entry.py            ← CLI Launcher utama
│   ├── config.py                ← Konfigurasi path & MQTT
│   └── publisher_brone.py       ← FER Publisher (mode-aware)
├── expression/REFINEMENT/       ← Pygame reference (research)
├── test_publisher.py            ← CLI tester (simple)
├── test_tts_publisher.py        ← CLI tester (full-featured)
├── mosquitto_brone.conf         ← Konfigurasi Mosquitto
└── docs/                        ← 📁 Dokumentasi lengkap
```

---

## Mode Operasi

```
  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
  │   DEFAULT    │     │    MIRROR    │     │  CONVERSATION    │
  │              │     │              │     │                  │
  │ • MediaPipe  │     │ • Python FER │     │ • Python FER     │
  │   aktif      │     │   aktif      │     │   aktif          │
  │ • Robot idle │     │ • Robot tiru │     │ • Robot berbicara│
  │   + tracking │     │   emosi user │     │   + tiru emosi   │
  │ • Kamera di  │     │ • Kamera di  │     │ • Kamera di      │
  │   browser    │     │   Python     │     │   Python         │
  └──────────────┘     └──────────────┘     └──────────────────┘
       [D key]              [M key]               [C key]
```

---

*Lihat [docs/01-architecture.md](docs/01-architecture.md) untuk penjelasan detail setiap mode.*
