# 06 · Head Pan & Anti-Shake Algorithm

← [05 · MQTT Protocol](05-mqtt-protocol.md) | [07 · TTS & Conversation →](07-tts-conversation.md)

---

## Daftar Isi

- [Konsep & Masalah yang Diselesaikan](#konsep--masalah-yang-diselesaikan)
- [Parameter Sistem](#parameter-sistem)
- [Two-Layer Anti-Shake Algorithm](#two-layer-anti-shake-algorithm)
- [State Variables](#state-variables)
- [Algoritma Lengkap (Pseudocode)](#algoritma-lengkap-pseudocode)
- [panHead() Function](#panhead-function)
- [Manual Override (Keyboard)](#manual-override-keyboard)
- [Debug Visualization](#debug-visualization)

---

## Konsep & Masalah yang Diselesaikan

### Tanpa Anti-Shake (Masalah)

```
Gaze X timeline (pengguna menoleh kanan):

  0.0 ──────────────────── 0.65 ── 0.67 ── 0.64 ── 0.68 ──
                                     ↑       ↑       ↑
                            Threshold   Noise berfluktuasi di sekitar threshold

  Hasil: HEAD_RIGHT, HEAD_LEFT, HEAD_RIGHT, HEAD_LEFT ... (jitter!)
  Robot: leher bergetar kanan-kiri terus-menerus
```

### Dengan Anti-Shake (Solusi)

```
Gaze X timeline:

  0.0 ──────────────────── 0.65 ── 0.70 ── 0.72 ── 0.68 ──▶
                                     ↑
                              Edge terdeteksi, timer mulai
                              ....100ms....200ms....300ms....400ms
                                                              ↑
                                                    Hold ≥ 400ms → FIRE!
                                                    (hanya 1 kali)

  Robot: leher bergerak SEKALI ke kanan → stabil ✓
```

---

## Parameter Sistem

```javascript
// app.js — Konstanta Head Pan

const HEAD_MAX_ANGLE   = 45;    // ° — batas maksimum ke kiri/kanan
const HEAD_MIN_ANGLE   = -45;   // ° — batas minimum
const HEAD_PAN_STEP    = 15;    // ° — per trigger event

const PUPIL_EDGE_THRESHOLD  = 0.65;  // gaze X harus melebihi ini
const EDGE_HOLD_REQUIRED    = 400;   // ms — durasi stabil di edge
const HEAD_COMMAND_INTERVAL = 600;   // ms — min gap antar perintah

const TELEMETRY_INTERVAL    = 150;   // ms — rate publish tracking_state
```

### Rentang Pergerakan

```
-45°   -30°   -15°    0°    +15°   +30°   +45°
  │      │      │      │      │      │      │
  ●──────●──────●──────●──────●──────●──────●
  L             ↑                          R
              Center
              (start)

Total 6 langkah kiri ke kanan.
Setiap panHead() mengubah currentAngle ± HEAD_PAN_STEP (15°).
```

---

## Two-Layer Anti-Shake Algorithm

### Layer 1: Hysteresis Hold (400ms)

```
SYARAT: gaze.x harus terus-menerus di luar threshold [0.65]
        selama 400ms sebelum head pan di-trigger.

Timeline (gaze berfluktuasi):

  t=0ms:   gaze.x = 0.70  [> 0.65]  → edgeHoldStart = now()
  t=100ms: gaze.x = 0.68  [> 0.65]  → hold = 100ms < 400ms  → WAIT
  t=200ms: gaze.x = 0.60  [< 0.65]  → RESET! edgeHoldStart = null
  t=300ms: gaze.x = 0.72  [> 0.65]  → edgeHoldStart = now()  (ulang)
  t=400ms: gaze.x = 0.75  [> 0.65]  → hold = 100ms < 400ms  → WAIT
  t=500ms: gaze.x = 0.73  [> 0.65]  → hold = 200ms < 400ms  → WAIT
  t=600ms: gaze.x = 0.71  [> 0.65]  → hold = 300ms < 400ms  → WAIT
  t=700ms: gaze.x = 0.74  [> 0.65]  → hold = 400ms ≥ 400ms  → ✅ CHECK LAYER 2

Kunci: Timer di-RESET setiap kali gaze kembali ke dalam threshold.
```

### Layer 2: Rate Limiting (600ms)

```
SYARAT: Minimal 600ms sejak perintah head pan terakhir.

  t=700ms: Layer 1 ✓ → cek lastCommandTime
    lastCommandTime = t=100ms (perintah sebelumnya)
    interval = 700 - 100 = 600ms ≥ 600ms → ✅ FIRE!
    panHead(direction='right', trigger='pupil_edge')
    lastCommandTime = t=700ms

  t=900ms: Layer 1 ✓ lagi → cek lastCommandTime
    interval = 900 - 700 = 200ms < 600ms → ⛔ BLOCKED

  t=1300ms: Layer 1 ✓ → cek lastCommandTime
    interval = 1300 - 700 = 600ms ≥ 600ms → ✅ FIRE!

Efek: Maksimum 1 perintah per 600ms.
```

---

## State Variables

```javascript
// State variables di dalam ExpressionApp class

this.currentHeadAngle   = 0;      // ° — posisi servo saat ini
this.edgeHoldStart      = null;   // timestamp saat gaze mulai di edge
this.lastHeadCommandTime = 0;     // timestamp perintah terakhir
```

---

## Algoritma Lengkap (Pseudocode)

```
startTrackingLoop():
    loop setiap frame:

        gaze = faceTracker.getGaze()   // { x: [-1,1], y: [-1,1] }

        // ─── EDGE DETECTION ─────────────────────────────────────
        atEdge = (|gaze.x| > PUPIL_EDGE_THRESHOLD)   // 0.65
        direction = (gaze.x > 0) ? +1 : -1           // +1=kanan, -1=kiri

        if atEdge:
            if edgeHoldStart === null:
                edgeHoldStart = Date.now()             // mulai timer

            holdDuration = Date.now() - edgeHoldStart  // berapa lama sudah di edge

            // ─── LAYER 1: Hysteresis Hold ─────────────────────
            if holdDuration >= EDGE_HOLD_REQUIRED:     // 400ms

                // ─── LAYER 2: Rate Limiting ───────────────────
                timeSinceLast = Date.now() - lastHeadCommandTime
                if timeSinceLast >= HEAD_COMMAND_INTERVAL:   // 600ms

                    // ─── FIRE! ────────────────────────────────
                    panHead(direction, 'pupil_edge')
                    edgeHoldStart = null  // reset setelah fire
        else:
            edgeHoldStart = null          // gaze kembali ke tengah → reset

        // ─── PUPIL UPDATE ────────────────────────────────────
        faceRenderer.setPupilOffset(gaze.x, gaze.y)

        // ─── TELEMETRY ───────────────────────────────────────
        if Date.now() - lastTelemetryTime >= TELEMETRY_INTERVAL:
            publishTrackingState()
            lastTelemetryTime = Date.now()

        requestAnimationFrame(loop)
```

---

## panHead() Function

```javascript
panHead(direction, trigger):
    // direction: +1 atau -1
    // trigger: 'pupil_edge', 'manual_key', 'reset'

    // Hitung angle baru
    newAngle = currentHeadAngle + (direction × HEAD_PAN_STEP)

    // Clamp ke batas
    newAngle = Math.max(HEAD_MIN_ANGLE, Math.min(HEAD_MAX_ANGLE, newAngle))
    atLimit  = (newAngle === HEAD_MIN_ANGLE || newAngle === HEAD_MAX_ANGLE)

    currentHeadAngle     = newAngle
    lastHeadCommandTime  = Date.now()

    // Publish ke MQTT
    mqttClient.publish('robot/head_control', {
        pan_deg:      newAngle,
        tilt_deg:     0,
        pan_norm:     newAngle / HEAD_MAX_ANGLE,    // normalize ke [-1, 1]
        trigger:      trigger,
        at_limit:     atLimit,
        timestamp_ms: Date.now()
    })

    // Update debug UI
    updateHeadControlDebug()
```

### Contoh Sequence panHead()

```
State awal: currentHeadAngle = 0°

Call: panHead(+1, 'pupil_edge')
  newAngle = 0 + (1 × 15) = 15°
  publish: { pan_deg: 15, pan_norm: 0.333, trigger: 'pupil_edge' }

Call: panHead(+1, 'pupil_edge')
  newAngle = 15 + 15 = 30°
  publish: { pan_deg: 30, pan_norm: 0.667 }

Call: panHead(+1, 'pupil_edge')
  newAngle = 30 + 15 = 45°
  atLimit = true
  publish: { pan_deg: 45, pan_norm: 1.0, at_limit: true }

Call: panHead(+1, 'pupil_edge')   ← CLAMP, tidak bergerak lagi
  newAngle = clamp(45+15, -45, 45) = 45°  (tidak berubah)
  at_limit = true
```

---

## Manual Override (Keyboard)

```javascript
// app.js — setupEventHandlers()

'ArrowLeft' → panHead(-1, 'manual_key')
'ArrowRight' → panHead(+1, 'manual_key')
'r' → resetHead()

resetHead():
    currentHeadAngle = 0
    lastHeadCommandTime = Date.now()
    mqttClient.publish('robot/head_control', {
        pan_deg: 0, tilt_deg: 0, pan_norm: 0,
        trigger: 'reset', at_limit: false,
        timestamp_ms: Date.now()
    })
```

**Catatan:** Manual override tidak melewati Layer 1 & Layer 2 (tidak ada delay).

---

## Debug Visualization

Panel debug menampilkan informasi real-time head pan:

```
╔═══════════════════════════════╗
║  HEAD CONTROL                 ║
╠═══════════════════════════════╣
║  Angle  │ ═══════[■]══  +15° ║  ← bar menunjukkan posisi
║  Gaze X │ 0.72              ║
║  Hold   │ ████░░░  320ms    ║  ← progress ke 400ms
║  Edge   │ ● ACTIVE          ║
║  Payload│ {"pan_deg":15,...} ║
╚═══════════════════════════════╝

Pan Angle Bar:
  -45°    0°    +45°
   ─────────┼─────────
        [■]         ← posisi saat ini
   ←────────┼────────→
   L       mid      R

Hold Progress Bar:
  □□□□□□□□□□  0ms    (tidak di edge)
  ████░░░░░░  160ms  (di edge, menuju 400ms)
  ██████████  400ms! → FIRE
```

---

← [05 · MQTT Protocol](05-mqtt-protocol.md) | [07 · TTS & Conversation →](07-tts-conversation.md)
