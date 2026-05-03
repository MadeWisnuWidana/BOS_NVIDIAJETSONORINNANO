# 08 · Deployment di NVIDIA Jetson

← [07 · TTS & Conversation](07-tts-conversation.md) | [09 · Debugging →](09-debugging-testing.md)

---

## Daftar Isi

- [Prasyarat Hardware & Software](#prasyarat-hardware--software)
- [Struktur Direktori Jetson](#struktur-direktori-jetson)
- [Instalasi Langkah demi Langkah](#instalasi-langkah-demi-langkah)
- [Konfigurasi config.py](#konfigurasi-configpy)
- [main-entry.py — CLI Launcher](#main-entrypy--cli-launcher)
- [Auto-Start & Kiosk Mode](#auto-start--kiosk-mode)
- [Optimasi Performa Jetson](#optimasi-performa-jetson)
- [Troubleshooting Umum](#troubleshooting-umum)

---

## Prasyarat Hardware & Software

```
Hardware:
  ✅ NVIDIA Jetson (Nano 4GB / Xavier NX / Orin Nano)
  ✅ Display (HDMI atau DSI)
  ✅ Webcam USB (UVC compatible, tested: Logitech C270/C920)
  ✅ Koneksi jaringan (untuk instalasi package)

Software:
  ✅ JetPack SDK 4.6+ (Ubuntu 20.04 base)
  ✅ Python 3.8+
  ✅ pip3
  ✅ git
  ✅ Chromium browser
```

---

## Struktur Direktori Jetson

```
~/brone-system/                         ← buat direktori ini
│
├── jetson-deploy/                      ← copy dari repo
│   ├── main-entry.py                   ← LAUNCHER UTAMA (jalankan ini)
│   ├── config.py                       ← ⚠️ EDIT SESUAI PATH ANDA
│   ├── publisher_brone.py              ← FER Publisher (mode-aware)
│   └── README.md
│
├── FER-V2/                             ← clone dari GitHub
│   ├── app/
│   │   └── publisher.py               ← (opsional, fallback)
│   ├── models/
│   │   └── fer_resnet34_v1.2.onnx     ← ⚠️ MODEL HARUS ADA DISINI
│   └── haarcascades/
│       └── haarcascade_frontalface_default.xml
│
└── IntegrateSpeechExpression/          ← clone dari GitHub
    ├── index.html
    ├── css/
    ├── js/
    └── ...
```

---

## Instalasi Langkah demi Langkah

### Step 1: Buat Workspace

```bash
mkdir ~/brone-system
cd ~/brone-system
```

### Step 2: Clone Repositories

```bash
# Clone display frontend
git clone https://github.com/FarrelPandhita/IntegrateSpeechExpression.git

# Clone FER-V2 (jika di repo terpisah)
# git clone https://github.com/FarrelPandhita/FER-BRONE.git FER-V2

# Copy jetson-deploy folder
cp -r IntegrateSpeechExpression/jetson-deploy ~/brone-system/
```

### Step 3: Instalasi Mosquitto MQTT Broker

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients

# Konfigurasi WebSocket
sudo nano /etc/mosquitto/conf.d/brone.conf
```

Isi file:
```
listener 1883
protocol mqtt
allow_anonymous true

listener 9001
protocol websockets
allow_anonymous true
```

```bash
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# Verifikasi
sudo systemctl status mosquitto
```

### Step 4: Instalasi Python Dependencies

```bash
# MQTT client
pip3 install paho-mqtt

# ONNX Runtime (Jetson — gunakan versi yang sesuai JetPack)
# Untuk JetPack 5.x (Ubuntu 20.04):
pip3 install onnxruntime

# Atau untuk GPU support (lebih baik):
# Download dari: https://elinux.org/Jetson_Zoo#ONNX_Runtime
pip3 install onnxruntime_gpu-*.whl

# OpenCV (biasanya sudah ada di JetPack)
pip3 install opencv-python
# Atau gunakan yang sudah ada:
python3 -c "import cv2; print(cv2.__version__)"
```

### Step 5: Edit config.py

```bash
nano ~/brone-system/jetson-deploy/config.py
```

```python
# config.py — Sesuaikan BASE_DIR dengan path Anda
BASE_DIR = os.path.expanduser("~/brone-system")

# Verifikasi path setelah diedit:
# python3 -c "import config; print(config.FER_PUBLISHER_PATCHED_PATH)"
```

### Step 6: Copy Model File

```bash
# Model ONNX harus ada di FER-V2/
ls ~/brone-system/FER-V2/fer_resnet34_v1.2.onnx
# Jika belum ada, copy dari komputer development:
# scp user@laptop:/path/to/model.onnx ~/brone-system/FER-V2/
```

### Step 7: Test Run

```bash
cd ~/brone-system/jetson-deploy
python3 main-entry.py
```

Expected output:
```
  Memulai BRONE System...
  → Menjalankan HTTP server di port 8080...
  ✓ Display tersedia di: http://localhost:8080
  → Menghubungkan ke MQTT broker...
  ✓ MQTT terhubung

╔══════════════════════════════════════════════════════╗
║       BRONE SYSTEM  —  Access Control CLI            ║
╠══════════════════════════════════════════════════════╣
║  Status : ● MQTT OK
║  Mode   : DEFAULT
║  FER    : ○ Off
╚══════════════════════════════════════════════════════╝

  Pilih fitur BRONE:

          1. Default Mode      — Idle face + gaze tracking
          2. Mirror Mode       — Robot meniru ekspresi user (FER)
          3. Conversation Mode — TTS speaking + FER antara ucapan

          4. Cek Status Sistem
          5. Test Speaking (kirim animasi mulut 3 detik)

          0. Exit (stop semua)

  Input > _
```

---

## Konfigurasi config.py

```python
# config.py — Semua konstanta yang perlu disesuaikan

import os

# ─── BASE DIR ─────────────────────────────────────────────
BASE_DIR = os.path.expanduser("~/brone-system")
# Ganti ini jika workspace di lokasi berbeda

# ─── FER PATHS ────────────────────────────────────────────
FER_PUBLISHER_PATH         = os.path.join(BASE_DIR, "FER-V2", "pub.py")
FER_PUBLISHER_PATCHED_PATH = os.path.join(BASE_DIR, "FER-V2", "app", "publisher.py")
# main-entry.py akan coba PATCHED_PATH dulu, fallback ke PATH

DISPLAY_SERVE_DIR = os.path.join(BASE_DIR, "IntegrateSpeechExpression")

# ─── MQTT SETTINGS ────────────────────────────────────────
MQTT_HOST    = "localhost"
MQTT_PORT    = 1883           # Python native port
MQTT_PORT_WS = 9001           # WebSocket (untuk browser)

# Topics (jangan ubah kecuali juga ubah di app.js)
TOPIC_MODE        = "robot/mode"
TOPIC_EXPRESSION  = "robot/expression"
TOPIC_FER_EMOTION = "robot/fer_emotion"
TOPIC_FER_GAZE    = "robot/fer_gaze"

# ─── DISPLAY SERVER ───────────────────────────────────────
DISPLAY_PORT = 8080
DISPLAY_URL  = f"http://localhost:{DISPLAY_PORT}"

# ─── FER SETTINGS ─────────────────────────────────────────
FER_CONFIDENCE_THRESHOLD = 0.50   # Sync dengan publisher_brone.py
CAMERA_INDEX = 0                   # Index kamera (/dev/video0)

# ─── VALID MODES ──────────────────────────────────────────
VALID_MODES = ["default", "mirror", "conversation"]
```

---

## main-entry.py — CLI Launcher

### Cara Kerja Internal

```
main-entry.py startup:
        │
        ├── 1. BroneSystem.__init__()
        │       ├── current_mode = 'default'
        │       ├── fer_process = None
        │       └── http_process = None
        │
        ├── 2. system.start_http_server()
        │       └── subprocess.Popen(
        │               ['python3', '-m', 'http.server', '8080'],
        │               cwd=DISPLAY_SERVE_DIR
        │           )
        │
        ├── 3. system.connect_mqtt()
        │       ├── mqtt.Client(VERSION2)
        │       ├── client.connect(MQTT_HOST, MQTT_PORT)
        │       └── client.loop_start()
        │
        └── 4. Interactive menu loop


set_mode('mirror'):
        │
        ├── stop_fer() jika sebelumnya mirror/conversation
        │
        ├── start_fer()
        │       └── subprocess.Popen(
        │               ['python3', FER_PUBLISHER_PATCHED_PATH],
        │               cwd=dirname(fer_path)
        │           )
        │
        └── publish_mode('mirror')
                └── mqtt: {"mode":"mirror","timestamp_ms":...}


shutdown():
        │
        ├── stop_fer() → terminate + wait (timeout 3s) → kill
        ├── stop_http_server()
        ├── mqtt.loop_stop()
        └── mqtt.disconnect()
```

### Opsi Menu CLI

```
┌──────────────────────────────────────────────────────────┐
│  1. Default Mode    → stop FER + publish mode=default    │
│  2. Mirror Mode     → start FER + publish mode=mirror    │
│  3. Conversation    → start FER + publish mode=conv      │
│  4. Status          → tampilkan status semua subsistem   │
│  5. Test Speaking   → publish expression=speaking 3s     │
│  0. Exit            → shutdown semua                     │
└──────────────────────────────────────────────────────────┘

Status output:
  MQTT Broker   : ✓ Connected
  Mode Aktif    : MIRROR
  FER Publisher : ✓ Running (PID 12345)
  HTTP Server   : ✓ Running (port 8080)
  Display URL   : http://localhost:8080
```

---

## Auto-Start & Kiosk Mode

### Chromium Kiosk

```bash
# Buat file autostart
mkdir -p ~/.config/autostart
nano ~/.config/autostart/brone-display.desktop
```

```ini
[Desktop Entry]
Type=Application
Name=BRONE Display
Exec=chromium-browser --kiosk \
     --noerrdialogs \
     --disable-infobars \
     --no-first-run \
     --enable-gpu-rasterization \
     --enable-zero-copy \
     --ignore-gpu-blocklist \
     http://localhost:8080
X-GNOME-Autostart-enabled=true
```

### Systemd Service untuk main-entry.py

```bash
sudo nano /etc/systemd/system/brone-system.service
```

```ini
[Unit]
Description=BRONE System Launcher
After=network.target mosquitto.service
Requires=mosquitto.service

[Service]
Type=simple
User=jetson
WorkingDirectory=/home/jetson/brone-system/jetson-deploy
ExecStart=/usr/bin/python3 main-entry.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable brone-system
sudo systemctl start brone-system

# Monitor log
journalctl -u brone-system -f
```

### Disable Screen Blanking

```bash
# Untuk GNOME (Jetson Desktop)
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.desktop.screensaver idle-activation-enabled false
gsettings set org.gnome.settings-daemon.plugins.power idle-dim false

# Atau via xset (untuk X11)
xset s off
xset -dpms
xset s noblank
```

---

## Optimasi Performa Jetson

### Mode Performa Maksimum

```bash
# Set ke max performance mode
sudo nvpmodel -m 0

# Maximize clock speeds
sudo jetson_clocks

# Verifikasi
sudo jetson_clocks --show
```

### Chromium Flags untuk Canvas Rendering

```bash
chromium-browser \
  --kiosk \
  --enable-gpu-rasterization \
  --enable-zero-copy \
  --ignore-gpu-blocklist \
  --disable-gpu-driver-bug-workarounds \
  --enable-native-gpu-memory-buffers \
  http://localhost:8080
```

### ONNX Runtime Optimasi

```python
# publisher_brone.py — Session options
import onnxruntime as ort

sess_options = ort.SessionOptions()
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

providers = [
    ('CUDAExecutionProvider', {
        'device_id': 0,
        'arena_extend_strategy': 'kNextPowerOfTwo',
    }),
    'CPUExecutionProvider'
]

session = ort.InferenceSession(
    Config.MODEL_PATH,
    sess_options=sess_options,
    providers=providers
)
print(f"Running on: {session.get_providers()[0]}")
```

---

## Troubleshooting Umum

### Mosquitto tidak bisa start

```bash
# Cek konflik port
sudo netstat -tulpn | grep -E '1883|9001'

# Lihat log detail
sudo journalctl -u mosquitto -n 50

# Restart
sudo systemctl restart mosquitto
```

### Browser tidak connect ke MQTT

```bash
# Test WebSocket
mosquitto_pub -h localhost -p 9001 -t test -m hello --protocol websockets

# Cek firewall
sudo ufw status
sudo ufw allow 9001   # jika perlu
```

### Kamera tidak bisa dibuka oleh Python

```bash
# Cek siapa yang memakai kamera
fuser /dev/video0

# Pastikan mode sudah di-switch ke mirror/conversation dulu
# (Browser harus lepas kamera sebelum Python ambil)

# Cek permission
ls -la /dev/video0
sudo usermod -aG video $USER  # tambah user ke grup video
```

### FER Model tidak ditemukan

```bash
# Cek path di config.py
python3 -c "
import sys; sys.path.insert(0, 'jetson-deploy')
from config import FER_PUBLISHER_PATCHED_PATH
import os
print('Path:', FER_PUBLISHER_PATCHED_PATH)
print('Exists:', os.path.exists(FER_PUBLISHER_PATCHED_PATH))
"

# Cek model ONNX
ls ~/brone-system/FER-V2/*.onnx
```

### Remote Control via SSH

```bash
# Dari laptop/PC di jaringan yang sama:
ssh jetson@<IP_JETSON>

# Remote switch mode
mosquitto_pub -h <IP_JETSON> -t "robot/mode" -m '{"mode":"mirror"}'

# Monitor semua topic
mosquitto_sub -h <IP_JETSON> -t "robot/#" -v
```

---

← [07 · TTS & Conversation](07-tts-conversation.md) | [09 · Debugging →](09-debugging-testing.md)
