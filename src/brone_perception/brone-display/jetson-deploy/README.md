# BRONE Jetson Deploy

Folder ini berisi file launcher untuk **deployment BRONE System di NVIDIA Jetson**.

---

## Struktur Folder yang Dibutuhkan di Jetson

```
~/brone-system/                      ← buat folder ini
├── jetson-deploy/                   ← copy folder ini dari repo
│   ├── main-entry.py                ← launcher utama
│   ├── config.py                    ← ⚠️ EDIT INI DULU
│   └── README.md
│
├── FER-BRONE/                       ← clone dari GitHub
│   └── publisher.py
│
└── IntegrateSpeechExpression/       ← clone dari GitHub (repo ini)
    └── index.html
```

---

## Langkah Setup di Jetson

### 1. Buat folder workspace
```bash
mkdir ~/brone-system
cd ~/brone-system
```

### 2. Clone repo
```bash
git clone https://github.com/FarrelPandhita/FER-BRONE.git
git clone https://github.com/FarrelPandhita/IntegrateSpeechExpression.git
```

### 3. Copy folder ini
```bash
cp -r IntegrateSpeechExpression/jetson-deploy ~/brone-system/jetson-deploy
```

### 4. Edit `config.py`
```bash
nano ~/brone-system/jetson-deploy/config.py
```
Sesuaikan `BASE_DIR` dengan path di Jetson kamu (default: `~/brone-system`).

### 5. Install dependencies
```bash
# MQTT broker
sudo apt install mosquitto mosquitto-clients -y

# Python MQTT client
pip3 install paho-mqtt

# FER dependencies
cd ~/brone-system/FER-BRONE
pip3 install -r requirements.txt
```

### 6. Konfigurasi Mosquitto (WebSocket untuk browser)
```bash
sudo nano /etc/mosquitto/mosquitto.conf
```
Tambahkan:
```
listener 1883
listener 9001
protocol websockets
allow_anonymous true
```
```bash
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
```

---

## Cara Menjalankan

```bash
cd ~/brone-system/jetson-deploy
python3 main-entry.py
```

Output:
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

## Remote Control via SSH

Dari komputer lain (pastikan terhubung ke network yang sama):

```bash
ssh jetson@<IP_JETSON>

# Switch ke mirror mode
mosquitto_pub -h localhost -t "robot/mode" -m '{"mode":"mirror"}'

# Switch ke conversation mode
mosquitto_pub -h localhost -t "robot/mode" -m '{"mode":"conversation"}'

# Kembali ke default
mosquitto_pub -h localhost -t "robot/mode" -m '{"mode":"default"}'

# Monitor semua topic (debug)
mosquitto_sub -h localhost -t "robot/#" -v
```

---

## Mode Reference

| Mode | Key | FER Aktif | Gaze | Cocok Untuk |
|------|-----|-----------|------|-------------|
| **Default** | `1` | ❌ | Browser MediaPipe | Idle / standby |
| **Mirror** | `2` | ✅ | Python (dari bbox) | Demo emosi real-time |
| **Conversation** | `3` | ✅ | Python (dari bbox) | Interaksi TTS + ekspresi |

---

## Troubleshooting

**MQTT tidak konek:**
```bash
sudo systemctl status mosquitto
sudo systemctl restart mosquitto
```

**FER tidak bisa buka kamera:**
```bash
# Pastikan tidak ada proses lain yang memakai kamera
# Di Default mode, browser memegang kamera. 
# Keluar dari Default mode dulu (pilih 2 atau 3)
ls /proc/*/fd | xargs ls -la 2>/dev/null | grep video0
```

**Display tidak terbuka:**
```bash
# Buka manual di Chromium
chromium-browser http://localhost:8080
```
