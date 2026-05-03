# 03 · Gaze Tracking — MediaPipe, Smoothing & Pupil Control

← [02 · Face Rendering](02-face-rendering.md) | [04 · FER Pipeline →](04-fer-pipeline.md)

---

## Daftar Isi

- [Overview Pipeline](#overview-pipeline)
- [MediaPipe Face Detection](#mediapipe-face-detection)
- [Kalkulasi Gaze dari BoundingBox](#kalkulasi-gaze-dari-boundingbox)
- [Dead Zone Filter](#dead-zone-filter)
- [EMA Smoothing](#ema-smoothing)
- [Fallback Mouse/Touch Mode](#fallback-mousetouch-mode)
- [No-Face Decay Behavior](#no-face-decay-behavior)
- [Camera Pause & Resume](#camera-pause--resume)
- [Parameter Tuning Guide](#parameter-tuning-guide)

---

## Overview Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                     face-tracker.js                                 │
│                                                                     │
│  Webcam 640×480                                                     │
│      │                                                              │
│      ▼                                                              │
│  MediaPipe FaceDetection (async, ~30fps)                           │
│      │                                                              │
│      │  results.detections[0].boundingBox                          │
│      │    xCenter ∈ [0,1]  (0=kiri, 1=kanan)                      │
│      │    yCenter ∈ [0,1]  (0=atas, 1=bawah)                      │
│      │                                                              │
│      ▼                                                              │
│  Raw Gaze Calculation                                               │
│      rawX = (xCenter - 0.5) × -2.0    ← mirror + normalize         │
│      rawY = (yCenter - 0.5) ×  2.0    ← normalize                  │
│      (hasil: rawX, rawY ∈ [-1, 1])                                  │
│      │                                                              │
│      ▼                                                              │
│  Dead Zone Filter                                                   │
│      if |rawX| < 0.04 → rawX = 0                                   │
│      if |rawY| < 0.04 → rawY = 0                                   │
│      │                                                              │
│      ▼                                                              │
│  Hard Clamp                                                         │
│      rawX = clamp(rawX, -1, 1)                                      │
│      rawY = clamp(rawY, -1, 1)                                      │
│      │                                                              │
│      ▼                                                              │
│  EMA Smoothing                                                      │
│      smoothX = smoothX × 0.60 + rawX × 0.40                        │
│      smoothY = smoothY × 0.60 + rawY × 0.40                        │
│      │                                                              │
│      ▼                                                              │
│  getGaze() → { x: smoothX, y: smoothY }                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
               app.js startTrackingLoop()
                   faceRenderer.setPupilOffset(x, y)
                   checkEdgeThreshold(x) → head pan
```

---

## MediaPipe Face Detection

### Konfigurasi Model

```javascript
// face-tracker.js
const faceDetection = new FaceDetection({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`
});

faceDetection.setOptions({
    model: 'short',           // ← model ringan, cocok untuk Jetson
    minDetectionConfidence: 0.5
});
```

**Mengapa model `short`?**

```
Model 'short':
  - Input: 128×128 px (ringan)
  - Optimized untuk wajah dekat (0–2 meter)
  - Cocok untuk webcam depan robot
  - Lebih cepat, akurasi cukup untuk gaze estimation

Model 'full':
  - Input: 256×256 px
  - Jangkauan lebih jauh
  - CPU lebih berat → hindari di Jetson Nano
```

### Cara Kerja Camera Utility

```
MediaPipe Camera Utility mengelola loop kamera secara asynchronous:

const camera = new Camera(videoElement, {
    onFrame: async () => {
        await faceDetection.send({ image: videoElement });
    },
    width: 640,
    height: 480
});

camera.start();

Alur:
  camera.start()
      │ mengambil frame dari videoElement
      ▼
  onFrame() dipanggil setiap frame
      │
      ▼
  faceDetection.send({ image })
      │ async inferensi
      ▼
  faceDetection.onResults(results)
      │
      └── updateGazeFromResults(results)
```

### Output BoundingBox

```
results.detections[0]:
{
  boundingBox: {
    xCenter: 0.48,   ← center horizontal (0=kiri, 1=kanan layar)
    yCenter: 0.42,   ← center vertical (0=atas, 1=bawah)
    width:   0.20,   ← lebar box (proporsi frame)
    height:  0.28    ← tinggi box
  }
}

Interpretasi:
  xCenter=0.48 → wajah hampir di tengah, sedikit ke kiri layar
  yCenter=0.42 → wajah sedikit di atas tengah layar
```

---

## Kalkulasi Gaze dari BoundingBox

### Mengapa Mirror?

Webcam menghadap pengguna → perlu di-mirror horizontal agar robot melirik ke arah yang benar:

```
Tanpa mirror:
  Pengguna gerak kanan  → xCenter naik (> 0.5)
  rawX = (xCenter - 0.5) × 2.0 = positif (kanan)
  Robot melirik KANAN ← salah! (harusnya kiri dari perspektif pengguna)

Dengan mirror:
  rawX = (xCenter - 0.5) × -2.0   ← tanda negatif = mirror
  Pengguna gerak kanan → robot melirik KIRI ✓ (perspektif pengguna)
```

### Formula Lengkap

```
Input:
  xCenter ∈ [0.0, 1.0]
  yCenter ∈ [0.0, 1.0]

Step 1 — Center offset:
  centeredX = xCenter - 0.5   → [-0.5, +0.5]
  centeredY = yCenter - 0.5   → [-0.5, +0.5]

Step 2 — Scale & Mirror:
  rawX = centeredX × -2.0     → [-1.0, +1.0]  (mirror horizontal)
  rawY = centeredY ×  2.0     → [-1.0, +1.0]  (tidak di-mirror vertikal)

Contoh kalkulasi:
  xCenter=0.2 (wajah di kiri layar):
    centeredX = 0.2 - 0.5 = -0.3
    rawX = -0.3 × -2.0 = +0.6  → robot melirik KANAN ✓

  xCenter=0.8 (wajah di kanan layar):
    centeredX = 0.8 - 0.5 = +0.3
    rawX = +0.3 × -2.0 = -0.6  → robot melirik KIRI ✓
```

---

## Dead Zone Filter

```
Tujuan: Mencegah mata robot "gemetar" saat pengguna diam (jitter dari noise deteksi)

  if |rawX| < DEAD_ZONE (0.04) → rawX = 0
  if |rawY| < DEAD_ZONE (0.04) → rawY = 0

Visualisasi:
                    Dead Zone
                  ←──0.08──→
  -1.0  ─────────┤  IGNORE  ├─────────  +1.0
                 -0.04    +0.04

  Nilai dalam zona [-0.04, +0.04] → diset ke 0
  Nilai di luar zona → dilewatkan normal

Efek:
  Tanpa dead zone: mata bergerak ±2px meski pengguna diam (noise)
  Dengan dead zone: mata tetap diam saat gaze di area tengah kecil
```

---

## EMA Smoothing

### Exponential Moving Average

```
Formula:
  smooth_t = smooth_(t-1) × α + raw_t × (1 - α)

  di mana α = smoothingFactor = 0.60

Artinya:
  60% dari nilai sebelumnya + 40% dari nilai baru

  → Nilai sebelumnya dominan → gerakan terasa lambat tapi mulus

Contoh sequence (α=0.60):
  
  t=0: smooth=0.0
  t=1: raw=0.8, smooth = 0.0×0.6 + 0.8×0.4 = 0.32
  t=2: raw=0.8, smooth = 0.32×0.6 + 0.8×0.4 = 0.512
  t=3: raw=0.8, smooth = 0.512×0.6 + 0.8×0.4 = 0.627
  t=4: raw=0.8, smooth = 0.627×0.6 + 0.8×0.4 = 0.696
  t=5: raw=0.8, smooth = 0.696×0.6 + 0.8×0.4 = 0.738
  ...  (converge menuju 0.8 secara asimtotik)

Response curve (raw berubah dari 0 ke 0.8 di t=1):

  0.8 │                    ────────── (raw)
      │              ─────╱
      │         ────╱
      │     ───╱
  0.0 │────╱
      └──────────────────────────────▶ time
       t=0  t=1  t=2  t=3  t=4  t=5
```

### Pengaruh Nilai α (smoothingFactor)

```
α = 0.30 (low, responsive)
  Reaksi cepat, tapi terlihat sedikit "jittery"
  Cocok untuk: kebutuhan real-time cepat

α = 0.60 (medium, default)
  Keseimbangan baik antara kecepatan & kemulusan
  Cocok untuk: gaze tracking normal

α = 0.85 (high, very smooth)
  Reaksi sangat lambat, delay terasa jelas
  Cocok untuk: input yang sangat noisy, atau efek mata "mengantuk"
```

---

## Fallback Mouse/Touch Mode

Jika kamera gagal diakses (permission ditolak atau sedang dipakai Python), sistem otomatis beralih ke input mouse/touch:

```
getUserMedia() gagal
        │
        ├── trackingMode = 'mouse'
        │
        └── _setupMouseFallback():
                document.addEventListener('mousemove', e => {
                    rawX = (e.clientX / window.innerWidth  - 0.5) × 2.0;
                    rawY = (e.clientY / window.innerHeight - 0.5) × 2.0;
                });
                document.addEventListener('touchmove', e => {
                    rawX = (touch.clientX / window.innerWidth  - 0.5) × 2.0;
                    rawY = (touch.clientY / window.innerHeight - 0.5) × 2.0;
                });

Smoothing mouse: α = 0.50 (lebih responsif dari kamera, karena mouse lebih presisi)

Debug dot color:
  Kamera mode → hijau/kuning
  Mouse mode  → biru (solid)
```

---

## No-Face Decay Behavior

Saat tidak ada wajah terdeteksi, gaze perlahan kembali ke tengah (tidak langsung snap):

```
Setiap frame tanpa deteksi wajah:

  smoothX *= 0.92   ← decay 8% per frame
  smoothY *= 0.92

  if |smoothX| < 0.01 → smoothX = 0   ← snap ke nol saat mendekati
  if |smoothY| < 0.01 → smoothY = 0

Visualisasi decay:
  t=0: smoothX = 0.80 (wajah keluar frame)
  t=1: smoothX = 0.80 × 0.92 = 0.736
  t=2: smoothX = 0.736 × 0.92 = 0.677
  t=3: smoothX = 0.677 × 0.92 = 0.623
  ...
  t=20: smoothX ≈ 0.13
  t=30: smoothX ≈ 0.04  → snap ke 0

Durasi kembali ke tengah: ~1-2 detik pada 30fps
```

---

## Camera Pause & Resume

```
FaceTracker.pause():
    │
    ├── mediaPipeCamera.stop()        ← hentikan loop kamera
    ├── videoStream.getTracks()
    │       .forEach(t => t.stop())   ← release device (penting!)
    └── trackingEnabled = false


FaceTracker.resume():
    │
    ├── getUserMedia({ video: { width:640, height:480 } })
    │       ── jika berhasil:
    │           videoElement.srcObject = stream
    │           mediaPipeCamera.start()
    │           trackingEnabled = true
    │       ── jika gagal:
    │           _setupMouseFallback()
    └── (async, non-blocking)

⚠️  PENTING: Selalu panggil pause() SEBELUM Python mengambil kamera.
    Urutan salah → "Device or resource busy" pada OpenCV.
```

---

## Parameter Tuning Guide

### Tabel Parameter Lengkap

| Parameter | File | Default | Range Aman | Efek |
|-----------|------|---------|------------|------|
| `smoothingFactor` | face-tracker.js | `0.60` | 0.3–0.8 | Responsiveness vs smoothness |
| `mouseSmoothFactor` | face-tracker.js | `0.50` | 0.3–0.7 | Smoothing untuk mode mouse |
| `deadZone` | face-tracker.js | `0.04` | 0.02–0.10 | Zona diam di tengah |
| `decayFactor` | face-tracker.js | `0.92` | 0.85–0.98 | Kecepatan kembali ke tengah |
| `decaySnapThreshold`| face-tracker.js | `0.01` | — | Snap ke nol |
| `minDetectionConfidence` | face-tracker.js | `0.5` | 0.3–0.8 | Sensitivitas deteksi |
| `MAX_PUPIL_SHIFT_X` | face-renderer.js | `20` | 10–30 | Batas gerak horizontal pupil |
| `MAX_PUPIL_SHIFT_Y` | face-renderer.js | `22` | 10–30 | Batas gerak vertikal pupil |

### Skenario Tuning

**Masalah: Mata terlalu "gelisah" (jitter)**
```
Naikkan smoothingFactor ke 0.75–0.80
Naikkan deadZone ke 0.06–0.08
```

**Masalah: Mata terlalu "lambat" merespons**
```
Turunkan smoothingFactor ke 0.40–0.50
```

**Masalah: Pupil keluar dari bola mata**
```
Turunkan MAX_PUPIL_SHIFT_X dan Y
Cek apakah Layer 3 (ctx.clip()) berjalan di fr-eyes.js
```

**Masalah: Kamera tidak terdeteksi di Jetson**
```
Cek /dev/video0 tidak dipakai proses lain:
  fuser /dev/video0

Atau paksa index kamera:
  getUserMedia({ video: { deviceId: { exact: deviceId } } })
```

---

← [02 · Face Rendering](02-face-rendering.md) | [04 · FER Pipeline →](04-fer-pipeline.md)
