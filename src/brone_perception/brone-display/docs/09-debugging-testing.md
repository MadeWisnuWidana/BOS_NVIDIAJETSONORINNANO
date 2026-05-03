# 09 · Debugging & Testing

← [08 · Deployment Jetson](08-deployment-jetson.md) | [README →](../README.md)

---

## Daftar Isi

- [Debug Panel Browser](#debug-panel-browser)
- [Keyboard Shortcuts Lengkap](#keyboard-shortcuts-lengkap)
- [test_publisher.py — Simple Tester](#test_publisherpy--simple-tester)
- [test_tts_publisher.py — Full Tester](#test_tts_publisherpy--full-tester)
- [CLI MQTT Monitoring](#cli-mqtt-monitoring)
- [Checklist Debugging Sistematis](#checklist-debugging-sistematis)
- [Interpretasi Error Umum](#interpretasi-error-umum)

---

## Debug Panel Browser

Tekan **`D`** di dalam browser untuk toggle debug panel. Panel terdiri dari beberapa section:

```
┌────────────────────────────────────┐
│  ● FACE DETECTED                   │  ← status dot + teks
├────────────────────────────────────┤
│  ┌──────────────────────────────┐  │
│  │                              │  │
│  │    [Mini Webcam Preview]     │  │  ← feed kamera 180×135
│  │    [Green bbox overlay]      │  │
│  │                              │  │
│  └──────────────────────────────┘  │
├────────────────────────────────────┤
│  HEAD CONTROL                      │
│  ──────────                        │
│  Angle  │ ─────[■]──────────  +15° │  ← visual bar
│  Gaze X │  0.72                    │
│  Hold   │ ███████░░░  280ms        │  ← progress bar
│  Edge   │ ● ACTIVE                 │
│  ──────────────────────────────    │
│  Last Payload:                     │
│  {"pan_deg":15,"pan_norm":0.33,   │  ← JSON payload
│   "trigger":"pupil_edge",...}     │
│  Press D to hide                   │  ← hint
└────────────────────────────────────┘
```

### Status Dot

| Warna | CSS Class | Kondisi |
|-------|-----------|---------|
| 🟢 Hijau menyala | `.detected` | Wajah terdeteksi oleh MediaPipe |
| 🟡 Kuning berkedip | `.searching` | Kamera aktif, tidak ada wajah |
| 🔵 Biru solid | `.mouse` | Mode mouse/touch (kamera tidak tersedia) |
| 🔴 Merah | `.error` | Error saat init kamera |
| ⚪ Abu-abu | (default) | Inisialisasi / belum dimulai |

### Mode Badge (Kanan Bawah)

```
[DEFAULT]       ← abu-abu gelap, tidak ada glow
[MIRROR]        ← biru terang, ada glow animasi
[CONVERSATION]  ← kuning, ada glow animasi
```

---

## Keyboard Shortcuts Lengkap

Semua shortcut didefinisikan di `app.js → setupEventHandlers()`:

### Expression Controls

| Key | Action | MQTT yang Dikirim |
|-----|--------|-----------------|
| `s` | Speaking 3 detik | `robot/expression: {expression:'speaking', duration:3}` |
| `i` atau `0` | Idle | `robot/expression: {expression:'idle', duration:0}` |
| `1` | Sad | `robot/expression: {expression:'sad', duration:0}` |
| `2` | Shock | `robot/expression: {expression:'shock', duration:0}` |
| `3` | Cry | `robot/expression: {expression:'cry', duration:0}` |
| `4` | Shy | `robot/expression: {expression:'shy', duration:0}` |
| `5` | Happier | `robot/expression: {expression:'happier', duration:0}` |

### System Controls

| Key | Action | Effect |
|-----|--------|--------|
| `d` | Toggle Debug Panel | Show/hide debug overlay |
| `t` | Toggle Face Tracking | Enable/disable MediaPipe (default mode only) |
| `r` | Reset Head | Pan angle ke 0°, publish `robot/head_control` trigger=reset |
| `←` | Pan Left | Pan angle -15°, publish `robot/head_control` trigger=manual_key |
| `→` | Pan Right | Pan angle +15°, publish `robot/head_control` trigger=manual_key |

### Mode Switching (jika diimplementasi di keyboard)

| Key | Action |
|-----|--------|
| `Shift+D` | Default Mode |
| `M` | Mirror Mode |
| `C` | Conversation Mode |

---

## test_publisher.py — Simple Tester

File `test_publisher.py` adalah CLI tester sederhana untuk development awal. Memiliki mode single-shot dan interactive.

### Mode Single Shot

```bash
# Kirim speaking 5 detik
python3 test_publisher.py --expression speaking --duration 5

# Kirim idle
python3 test_publisher.py --expression idle

# Kirim ke broker remote
python3 test_publisher.py --host 192.168.1.100 --expression speaking --duration 3

# Kirim ke topic custom
python3 test_publisher.py --topic custom/topic --expression speaking
```

### Mode Interactive (--loop)

```bash
python3 test_publisher.py --loop

=== Interactive Mode ===
Commands:
  s <duration>  - Send speaking expression
  i             - Send idle expression
  q             - Quit
========================

Enter command: s 3
→ Sending: {"expression": "speaking", "duration": 3.0}
✓ Message published (id: 1)

Enter command: i
→ Sending: {"expression": "idle", "duration": 0}
✓ Message published (id: 2)

Enter command: q
Disconnected
```

---

## test_tts_publisher.py — Full Tester

Versi lengkap yang mensimulasikan semua skenario produksi.

### Session Contoh

```bash
python3 test_tts_publisher.py

╔══════════════════════════════════════════════════════════╗
║          BRONE — Dummy TTS / Expression Publisher        ║
╠══════════════════════════════════════════════════════════╣
║  Ketik 'help' untuk daftar perintah.                    ║
╚══════════════════════════════════════════════════════════╝

✅ MQTT connected (localhost:1883)

  brone> help

  ╔══════════════════════════════════════════════════════════╗
  ║                    Available Commands                    ║
  ... (lihat tabel di docs/07-tts-conversation.md)
  ╚══════════════════════════════════════════════════════════╝

  brone> speak 5
  → robot/expression: speaking 5.0s

  brone> fer neutral
  → robot/fer_emotion: Neutral → idle (conf: 0.92)

  brone> mode mirror
  → robot/mode: mirror

  brone> fer happy
  → robot/fer_emotion: Happy → happier (conf: 0.92)

  brone> mode default
  → robot/mode: default

  brone> quit
  👋 Bye!
```

### Emotion Mapping di test_tts_publisher.py

```python
EMOTION_TO_EXPRESSION = {
    "happy":    "happier",
    "neutral":  "idle",
    "sad":      "sad",
    "shocked":  "shock",
    "upset":    "cry",
}
```

---

## CLI MQTT Monitoring

### Monitor Semua Topic

```bash
mosquitto_sub -t "robot/#" -v
```

Output contoh:
```
robot/expression {"expression":"speaking","duration":3.0}
robot/head_control {"pan_deg":15.0,"tilt_deg":0,"pan_norm":0.333,...}
robot/tracking_state {"face_detected":true,"raw_gaze_x":0.45,...}
robot/fer_emotion {"emotion":"Happy","expression":"happier","confidence":0.85}
```

### Monitor Topic Spesifik

```bash
# Head control saja
mosquitto_sub -t "robot/head_control" -v

# FER emotion saja
mosquitto_sub -t "robot/fer_emotion" -v

# Telemetri tracking
mosquitto_sub -t "robot/tracking_state" -v
```

### Pretty Print JSON

```bash
# macOS/Linux: pipe ke python json
mosquitto_sub -t "robot/#" | while read line; do
    echo "---"
    echo "$line" | python3 -c "
import sys, json
line = sys.stdin.read()
try:
    topic, *rest = line.split(' ', 1)
    payload = json.loads(rest[0] if rest else '{}')
    print(f'Topic: {topic}')
    print(json.dumps(payload, indent=2))
except:
    print(line)
"
done
```

### Publish Manual dari CLI

```bash
# Test ekspresi
mosquitto_pub -t "robot/expression" -m '{"expression":"speaking","duration":3}'

# Test mode switch
mosquitto_pub -t "robot/mode" -m '{"mode":"mirror","timestamp_ms":0}'

# Simulasi FER emotion
mosquitto_pub -t "robot/fer_emotion" -m '{
    "emotion":"Happy",
    "expression":"happier",
    "confidence":0.85,
    "timestamp":0
}'

# Reset head
mosquitto_pub -t "robot/head_control" -m '{
    "pan_deg":0,
    "tilt_deg":0,
    "pan_norm":0,
    "trigger":"reset",
    "at_limit":false,
    "timestamp_ms":0
}'
```

---

## Checklist Debugging Sistematis

### Level 1: Apakah Mosquitto Berjalan?

```bash
# Linux
sudo systemctl status mosquitto

# Windows
Get-Service -Name mosquitto

# Test publish-subscribe sederhana:
# Terminal 1:
mosquitto_sub -t test -v

# Terminal 2:
mosquitto_pub -t test -m "hello"

# Jika Terminal 1 menampilkan "test hello" → MQTT OK ✓
```

### Level 2: Apakah Browser Terhubung ke MQTT?

```
1. Buka browser di http://localhost:8080
2. Lihat status indicator kanan atas:
   - "● MQTT" dengan dot hijau → Terhubung ✓
   - "● MQTT" dengan dot merah → TIDAK terhubung ✗

Jika tidak terhubung:
  - Cek apakah port 9001 (WebSocket) open:
    netstat -an | grep 9001
  - Cek konfigurasi Mosquitto WebSocket listener
```

### Level 3: Apakah MQTT Message Terkirim ke Browser?

```bash
# Di terminal, kirim ekspresi:
mosquitto_pub -t "robot/expression" -m '{"expression":"sad","duration":0}'

# Di browser, robot harus tampilkan ekspresi sedih dalam 0.1 detik

# Jika tidak berubah:
  - Cek topic yang di-subscribe di mqtt-client.js
  - Pastikan topic SAMA PERSIS (case sensitive)
  - Buka browser console (F12) → cari error MQTT
```

### Level 4: Apakah FaceTracker Berjalan?

```
1. Tekan D → cek debug panel
2. Status dot harus:
   - Hijau (wajah terdeteksi)
   - Kuning berkedip (mencari wajah)
   - Biru (mode mouse)

Jika merah (error):
  - Izin kamera ditolak browser?
    → Klik ikon kunci di address bar → allow kamera
  
  - Kamera sedang dipakai Python?
    → Ganti ke default mode dulu
    → Atau pastikan Python sudah dimatikan
  
  - /dev/video0 tidak ada?
    ls /dev/video*
```

### Level 5: Apakah Head Pan Berfungsi?

```bash
# Monitor head control
mosquitto_sub -t "robot/head_control" -v

# Gerakkan wajah ke kiri/kanan di depan kamera
# Atau tekan ← → di keyboard

# Harus muncul payload di terminal

Jika tidak ada payload:
  - Debug panel: apakah gaze X melebihi 0.65?
  - Apakah edgeHoldStart tereset? (gaze kembali ke tengah sebelum 400ms)
```

### Level 6: Apakah FER Publisher Berjalan?

```bash
# Switch ke mirror mode dulu
mosquitto_pub -t "robot/mode" -m '{"mode":"mirror","timestamp_ms":0}'

# Jalankan FER publisher
python3 jetson-deploy/publisher_brone.py

# Monitor output
mosquitto_sub -t "robot/fer_emotion" -v

# Taruh wajah di depan kamera
# Harus muncul: robot/fer_emotion {"emotion":"Happy","expression":"happier",...}
```

---

## Interpretasi Error Umum

### `Connection refused` saat connect MQTT

```
Cause: Mosquitto tidak berjalan atau port salah

Fix:
  sudo systemctl start mosquitto
  # atau
  mosquitto -v -c mosquitto_brone.conf

Cek port:
  netstat -an | grep -E '1883|9001'
```

### `NotAllowedError: Permission denied` di browser

```
Cause: Browser memblokir akses kamera

Fix:
  1. Klik ikon kamera/kunci di address bar
  2. Pilih "Allow" untuk kamera
  3. Refresh halaman

Atau (Chromium):
  --unsafely-treat-insecure-origin-as-secure=http://localhost:8080
```

### `Device or resource busy` di Python

```
Cause: Kamera sedang dipakai browser (MediaPipe)

Fix:
  1. Switch ke mirror mode via MQTT terlebih dahulu:
     mosquitto_pub -t "robot/mode" -m '{"mode":"mirror","timestamp_ms":0}'
  2. Tunggu 1-2 detik
  3. Baru jalankan publisher Python

Detail: docs/01-architecture.md#mekanisme-switch-kamera
```

### Robot ekspresi tidak berubah meski FER kirim data

```
Possible causes:

1. Mode tidak sesuai
   Cek: Apakah browser dalam mode mirror/conversation?
   Fix: mosquitto_pub -t "robot/mode" -m '{"mode":"mirror","timestamp_ms":0}'

2. Confidence terlalu rendah
   Cek: apakah confidence ≥ 0.50 di payload?
   Fix: naikkan cahaya atau dekatkan wajah ke kamera

3. Topic tidak match
   Cek: publisher menulis ke robot/fer_emotion?
   mosquitto_sub -t "robot/#" -v
```

### Ekspresi berubah terlalu cepat (flickering)

```
Cause: Temporal averaging buffer belum terisi (< 2 frame)
       atau confidence threshold terlalu rendah

Fix (publisher_brone.py):
  Config.WINDOW_SIZE = 30          # naikkan buffer
  Config.CONFIDENCE_THRESHOLD = 0.60  # naikkan threshold

Fix (app.js):
  Tambahkan cooldown minimum antar state change:
  if (Date.now() - lastStateChange < 1000) return;  // 1 detik minimum
```

### Debug Panel tidak muncul

```
Cause: Tombol D tidak ter-handle

Check:
  Buka browser console (F12) → cek error JavaScript
  
  Pastikan app.js ter-load:
  console.log(typeof ExpressionApp)  // harus 'function', bukan 'undefined'

  Pastikan tidak ada error saat init:
  window.onerror = (msg, src, line) => console.error(msg, src, line)
```

---

← [08 · Deployment Jetson](08-deployment-jetson.md) | [README →](../README.md)
