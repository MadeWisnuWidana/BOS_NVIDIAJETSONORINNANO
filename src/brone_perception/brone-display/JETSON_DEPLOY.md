# Jetson Deployment Guide - MQTT Expression Display

Panduan lengkap untuk deploy MQTT Expression Display di NVIDIA Jetson.

## Prasyarat

- NVIDIA Jetson (Nano, Xavier, Orin, dll)
- JetPack SDK terinstall
- Koneksi internet untuk instalasi package

---

## 1. Instalasi Mosquitto MQTT Broker

### Install Mosquitto

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
```

### Konfigurasi WebSocket Support

Buat file konfigurasi untuk mengaktifkan WebSocket:

```bash
sudo nano /etc/mosquitto/conf.d/websocket.conf
```

Tambahkan konten berikut:

```
# Default MQTT listener
listener 1883

# WebSocket listener (untuk browser)
listener 9001
protocol websockets

# Allow anonymous connections (untuk development)
allow_anonymous true
```

### Restart Mosquitto

```bash
sudo systemctl restart mosquitto
sudo systemctl enable mosquitto
```

### Verifikasi

```bash
# Check status
sudo systemctl status mosquitto

# Test subscribe (terminal 1)
mosquitto_sub -t "robot/expression" -v

# Test publish (terminal 2)
mosquitto_pub -t "robot/expression" -m '{"expression":"speaking","duration":3}'
```

---

## 2. Setup Web Server

### Opsi A: Python HTTP Server (Simple)

```bash
cd /path/to/IntegrateSpeechExpression
python3 -m http.server 8080
```

Akses di browser: `http://localhost:8080`

### Opsi B: Nginx (Production)

```bash
sudo apt install -y nginx
```

Konfigurasi Nginx:

```bash
sudo nano /etc/nginx/sites-available/expression-display
```

```nginx
server {
    listen 8080;
    server_name localhost;
    
    root /home/jetson/IntegrateSpeechExpression;
    index index.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
}
```

Enable dan restart:

```bash
sudo ln -s /etc/nginx/sites-available/expression-display /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 3. Auto-Start dengan Systemd

### Service untuk Web Server (Python)

```bash
sudo nano /etc/systemd/system/expression-display.service
```

```ini
[Unit]
Description=Expression Display Web Server
After=network.target mosquitto.service

[Service]
Type=simple
User=jetson
WorkingDirectory=/home/jetson/IntegrateSpeechExpression
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable expression-display
sudo systemctl start expression-display
```

---

## 4. Auto-Launch Browser di Boot

### Chromium Kiosk Mode

Buat script autostart:

```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/expression-display.desktop
```

```ini
[Desktop Entry]
Type=Application
Name=Expression Display
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:8080
X-GNOME-Autostart-enabled=true
```

### Disable Screen Blanking

```bash
# Disable screen saver
gsettings set org.gnome.desktop.screensaver lock-enabled false
gsettings set org.gnome.desktop.screensaver idle-activation-enabled false

# Disable power management
gsettings set org.gnome.settings-daemon.plugins.power idle-dim false
```

---

## 5. Struktur Direktori yang Direkomendasikan

```
/home/jetson/
├── IntegrateSpeechExpression/     # Expression Display (web)
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── ...
├── SpeechPublisher/               # Program lain yang mengirim data
│   └── publisher.py
└── logs/                          # Log files
```

---

## 6. Testing

### Test dari Terminal

```bash
# Install Python MQTT client
pip3 install paho-mqtt

# Run test publisher
cd /home/jetson/IntegrateSpeechExpression
python3 test_publisher.py --loop
```

### Test dari Browser

1. Buka `http://localhost:8080`
2. Tekan `s` untuk test speaking (3 detik)
3. Tekan `i` untuk idle
4. Tekan `d` untuk toggle status indicator

---

## 7. Integrasi dengan Publisher Lain

Publisher Anda harus mengirim JSON ke topic `robot/expression`:

```python
import paho.mqtt.client as mqtt
import json

client = mqtt.Client()
client.connect("localhost", 1883)

# Ketika speech dimulai
speech_duration = 5.0  # detik
payload = json.dumps({
    "expression": "speaking",
    "duration": speech_duration
})
client.publish("robot/expression", payload)

# Atau untuk kembali ke idle
client.publish("robot/expression", json.dumps({
    "expression": "idle",
    "duration": 0
}))
```

---

## 8. Troubleshooting

### Mosquitto tidak bisa start

```bash
# Check logs
sudo journalctl -u mosquitto -f

# Check port conflicts
sudo netstat -tulpn | grep -E '1883|9001'
```

### Browser tidak connect ke MQTT

- Pastikan WebSocket listener aktif di port 9001
- Check firewall: `sudo ufw status`
- Buka firewall jika perlu: `sudo ufw allow 9001`

### Animasi patah-patah

- Pastikan GPU acceleration aktif di browser
- Kurangi animasi lain yang berjalan
- Check CPU usage: `htop`

---

## 9. Konfigurasi URL Parameters

Display mendukung konfigurasi via URL:

```
http://localhost:8080?mqtt_host=192.168.1.100&mqtt_port=9001&mqtt_topic=custom/topic
```

| Parameter | Default | Deskripsi |
|-----------|---------|-----------|
| `mqtt_host` | localhost | Host MQTT broker |
| `mqtt_port` | 9001 | Port WebSocket MQTT |
| `mqtt_topic` | robot/expression | Topic untuk subscribe |

---

## 10. Performance Tips untuk Jetson

1. **Gunakan Mode Performance**:
   ```bash
   sudo nvpmodel -m 0  # Max performance mode
   sudo jetson_clocks  # Max clock speeds
   ```

2. **Disable Desktop Effects**:
   - Settings → Appearance → Disable animations

3. **Browser Flags** (Chromium):
   ```
   --enable-gpu-rasterization
   --enable-zero-copy
   --ignore-gpu-blocklist
   ```
