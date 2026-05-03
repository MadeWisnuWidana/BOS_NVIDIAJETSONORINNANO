# 07 · TTS & Conversation Mode

← [06 · Head Pan](06-head-pan-antishake.md) | [08 · Deployment →](08-deployment-jetson.md)

---

## Daftar Isi

- [Konsep Conversation Mode](#konsep-conversation-mode)
- [Speaking Animation — Cara Kerja Teknis](#speaking-animation--cara-kerja-teknis)
- [Prioritas Ekspresi di Conversation Mode](#prioritas-ekspresi-di-conversation-mode)
- [Integrasi TTS Eksternal](#integrasi-tts-eksternal)
- [test_tts_publisher.py — Panduan Lengkap](#test_tts_publisherpy--panduan-lengkap)
- [Skenario Demo Lengkap](#skenario-demo-lengkap)

---

## Konsep Conversation Mode

```
DEFAULT MODE:
  Robot idle, melirik pengguna. Tidak ada dialog.

MIRROR MODE:
  Robot meniru emosi pengguna real-time via FER.

CONVERSATION MODE:
  Gabungan keduanya dengan PRIORITAS:

  ┌────────────────────────────────────────────────────────┐
  │            CONVERSATION MODE STATE MACHINE             │
  │                                                        │
  │  IDLE ──── TTS mulai ──── SPEAKING ──── TTS selesai   │
  │    ↑                          │               │        │
  │    │                          │               ▼        │
  │    │           (FER data)     │          FER dominan   │
  │    │         ↓                │          (ekspresi     │
  │    └── emosi via FER ◄────── ┘          dari kamera)  │
  │         saat idle                                      │
  └────────────────────────────────────────────────────────┘

  Prioritas speaking > fer_emotion:
    Jika sedang speaking → abaikan fer_emotion
    Jika tidak speaking  → tampilkan fer_emotion
```

---

## Speaking Animation — Cara Kerja Teknis

### Flow Teknis

```
Trigger: MQTT robot/expression { expression: 'speaking', duration: 3.0 }
        │
        ▼
app.js: handleExpressionMessage(data)
        │
        ▼
app.js: startSpeaking(3.0)
        │
        ├── clearTimeout(speakingTimer)   ← cancel timer sebelumnya
        │
        ├── faceRenderer.startSpeaking()
        │       │
        │       ├── this.state = 'speaking'
        │       └── this.speakingPhase = 0  ← mulai dari fase 0
        │
        └── speakingTimer = setTimeout(() => {
                stopSpeaking()
            }, 3000)


Setiap frame (60fps) saat state='speaking':

  updateSpeaking(deltaTime):
      speakingPhase += speakingSpeed × deltaTime
      // speakingSpeed = 4 rad/detik ≈ 0.64 siklus/detik
      // = mulut buka-tutup ≈ 2 kali per detik

      if speakingPhase > 2π → speakingPhase -= 2π  ← wrap

  drawFace():
      FRMouths.drawSpeaking(ctx, t, this.speakingPhase)


Setelah 3000ms:

  stopSpeaking()
      │
      ├── clearTimeout(speakingTimer)
      └── faceRenderer.stopSpeaking()
              │
              ├── this.state = 'idle'
              └── (transisi mulus via blink-swap)
```

### Oscillation Mathematics

```
Tinggi mulut (mouthHeight) berubah secara sinusoidal:

  mouthHeight = BASE_H + AMPLITUDE × sin(speakingPhase)

  BASE_H    = 30 px  (virtual 800×600 space)
  AMPLITUDE = 25 px

Nilai mouthHeight per fase:
  phase=0     → 30 + 25×sin(0)   = 30px  (tertutup)
  phase=π/4   → 30 + 25×0.707   = 48px
  phase=π/2   → 30 + 25×1.0     = 55px  (terbuka max)
  phase=3π/4  → 30 + 25×0.707   = 48px
  phase=π     → 30 + 25×0.0     = 30px  (tertutup)
  phase=5π/4  → 30 + 25×-0.707  = 12px  (lebih tertutup dari normal)
  ...

Tampilan visual:

  phase=0 (tertutup)    phase=π/2 (terbuka)    phase=π (tertutup)
  ╭────────────╮         ╭────────────╮         ╭────────────╮
  │            │         │            │         │            │
  ╰────────────╯         │            │         ╰────────────╯
                          │  (dalam)  │
                          ╰────────────╯
```

---

## Prioritas Ekspresi di Conversation Mode

```javascript
// app.js — handleFerEmotion(data)

handleFerEmotion(data) {
    // Hanya aktif di mirror/conversation mode
    if (this.currentMode === 'default') return;

    // ⚠️ PRIORITAS: Jangan interrupt speaking
    if (this.currentMode === 'conversation' && this.isSpeaking) {
        return;  // ← abaikan FER saat robot sedang bicara
    }

    // Confidence gate
    if (data.confidence < 0.50) return;

    // Terapkan ekspresi FER
    faceRenderer.setState(data.expression);
}
```

### Timeline Conversation Mode

```
t=0s   Robot idle (state='idle')
        │
t=1s   TTS mulai, kirim speaking 5s
        │   robot/expression: {expression:'speaking', duration:5}
        ▼
        Robot state='speaking', mulut bergerak
        │
        │   (saat speaking, FER data diabaikan)
        │   fer_emotion: {expression:'happier', confidence:0.8} → IGNORED
        │
t=6s   TTS selesai (timer habis)
        │
        ▼
        stopSpeaking() → state='idle'
        │
        │   (setelah selesai, FER kembali aktif)
        │   fer_emotion: {expression:'happier', confidence:0.8} → APPLIED ✓
        ▼
        Robot state='happier', menampilkan ekspresi happy

        ... dst, siklus berlanjut
```

---

## Integrasi TTS Eksternal

Sistem BRONE tidak menyertakan TTS engine — ia hanya menerima **event** dari TTS eksternal. Format:

```
TTS System (eksternal)        MQTT Broker          BRONE Display
──────────────────────        ───────────          ─────────────

TTS.speak("Hello!")
    │
    ├── Hitung durasi speech
    │   duration = text.length / chars_per_second
    │
    └── publish MQTT:
        topic: robot/expression
        payload: {
            "expression": "speaking",
            "duration": duration
        }
                    │
                    ▼
            Mosquitto broker
                    │
                    ▼
            Browser menerima
            mulut bergerak
            selama [duration] detik
```

### Implementasi Publisher TTS Sederhana

```python
import paho.mqtt.client as mqtt
import json, time

def send_tts_speaking(client, text, wpm=130):
    """
    Kirim speaking animation berdasarkan teks TTS.
    wpm = words per minute (rata-rata manusia: 120-150)
    """
    words    = len(text.split())
    duration = (words / wpm) * 60      # konversi ke detik
    duration = max(duration, 0.5)      # minimal 0.5 detik

    client.publish("robot/expression", json.dumps({
        "expression": "speaking",
        "duration": round(duration, 1)
    }))
    return duration


# Contoh penggunaan:
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("localhost", 1883)
client.loop_start()

texts = [
    "Halo, nama saya BRONE!",
    "Senang bertemu dengan kamu.",
    "Hari ini cuaca sangat bagus ya."
]

for text in texts:
    dur = send_tts_speaking(client, text)
    print(f"Speaking: '{text}' ({dur:.1f}s)")
    # Jalankan TTS di sini (misalnya: tts_engine.say(text))
    time.sleep(dur + 0.3)  # tunggu selesai + buffer

client.loop_stop()
client.disconnect()
```

---

## test_tts_publisher.py — Panduan Lengkap

File `test_tts_publisher.py` adalah **interactive REPL** untuk testing seluruh sistem dari terminal.

### Menjalankan

```bash
python3 test_tts_publisher.py
```

### Semua Perintah

```
╔══════════════════════════════════════════════════════════╗
║                    Available Commands                    ║
╠══════════════════════════════════════════════════════════╣
║  speak <detik>     Speaking animation (TTS simulasi)    ║
║                    Contoh: speak 3 → mulut gerak 3 det  ║
║                                                         ║
║  fer <emosi>       Simulasi FER emotion detection       ║
║                    Values: happy/neutral/sad/shocked/up  ║
║                    Contoh: fer happy → happier state     ║
║                                                         ║
║  expr <state>      Raw expression command               ║
║                    Values: idle/happy/sad/shock/cry/shy  ║
║                            /happier/speaking             ║
║                    Contoh: expr cry                      ║
║                                                         ║
║  mode <mode>       Switch display mode                  ║
║                    Values: default/mirror/conversation   ║
║                    Contoh: mode mirror                   ║
║                                                         ║
║  idle              Shortcut: kembali ke idle            ║
║  help              Tampilkan bantuan ini                 ║
║  quit / exit       Keluar                               ║
╚══════════════════════════════════════════════════════════╝
```

### Mapping Perintah ke MQTT

```
speak 3
  → publish robot/expression: {"expression":"speaking","duration":3.0}

fer happy
  → publish robot/fer_emotion: {
      "emotion":"Happy", "expression":"happier", "confidence":0.92
    }

fer sad
  → publish robot/fer_emotion: {
      "emotion":"Sad", "expression":"sad", "confidence":0.92
    }

expr cry
  → publish robot/expression: {"expression":"cry","duration":0}

mode mirror
  → publish robot/mode: {"mode":"mirror","timestamp_ms":...}

idle
  → publish robot/expression: {"expression":"idle","duration":0}
```

### Shortcut Langsung

```bash
# Perintah langsung tanpa prompt (untuk scripting)
echo "speak 5" | python3 test_tts_publisher.py

# Atau gunakan argparse pada test_publisher.py (versi simple):
python3 test_publisher.py --expression speaking --duration 3
python3 test_publisher.py --expression idle
python3 test_publisher.py --loop   # mode interaktif
```

---

## Skenario Demo Lengkap

### Skenario 1: Demo Basic Expressions

```bash
# Terminal 1: Buka display
python3 -m http.server 8080 &
chromium-browser http://localhost:8080

# Terminal 2: Test expressions
python3 test_tts_publisher.py

brone> speak 3         # robot berbicara 3 detik
brone> fer happy       # robot bahagia
brone> expr shock      # robot terkejut
brone> expr cry        # robot menangis
brone> idle            # kembali normal
```

### Skenario 2: Demo Conversation Mode

```bash
brone> mode conversation   # switch ke conversation mode
                            # (FER Python harus sudah jalan)

brone> speak 4             # robot berbicara 4 detik
                            # (selama speaking, FER diabaikan)
                            # (setelah 4 detik, FER kembali aktif)

brone> speak 2             # speak lagi...
brone> mode default        # kembali ke default
```

### Skenario 3: Simulasi Dialog Robot

```python
# simulate_dialog.py — contoh script dialog otomatis
import paho.mqtt.client as mqtt
import json, time

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("localhost", 1883)
client.loop_start()

def speak(text, wpm=130):
    words = len(text.split())
    dur = max((words/wpm)*60, 0.5)
    client.publish("robot/expression", json.dumps({
        "expression": "speaking", "duration": round(dur, 1)
    }))
    time.sleep(dur + 0.4)

def show_emotion(expr, hold=2.0):
    client.publish("robot/expression", json.dumps({
        "expression": expr, "duration": 0
    }))
    time.sleep(hold)

# Dialog sequence
time.sleep(1)
speak("Halo! Perkenalkan, saya adalah BRONE.")
time.sleep(0.3)
show_emotion("happier", 1.5)
speak("Saya bisa menampilkan berbagai ekspresi wajah.")
time.sleep(0.3)
show_emotion("sad", 1.5)
speak("Seperti ekspresi sedih seperti ini.")
time.sleep(0.3)
show_emotion("shock", 1.5)
speak("Atau terkejut!")
time.sleep(0.3)
show_emotion("idle", 0.5)
speak("Senang bertemu dengan kamu!")
show_emotion("happier", 2.0)

client.loop_stop()
client.disconnect()
```

---

← [06 · Head Pan](06-head-pan-antishake.md) | [08 · Deployment →](08-deployment-jetson.md)
