# 02 · Face Rendering — Ekspresi, Fungsi, & Koordinat

← [01 · Arsitektur](01-architecture.md) | [03 · Gaze Tracking →](03-gaze-tracking.md)

---

## Daftar Isi

- [Koordinat Sistem & FRTransform](#koordinat-sistem--frtransform)
- [Render Loop & Lifecycle](#render-loop--lifecycle)
- [State Machine Ekspresi](#state-machine-ekspresi)
- [Blink-Swap Algorithm](#blink-swap-algorithm)
- [Menggambar Mata (fr-eyes.js)](#menggambar-mata-fr-eyesjs)
- [Menggambar Mulut (fr-mouths.js)](#menggambar-mulut-fr-mouthsjs)
- [Kabel, Blush & Bintang (fr-cables.js)](#kabel-blush--bintang-fr-cablesjs)
- [Pupil Offset & Constraint System](#pupil-offset--constraint-system)
- [Speaking Animation](#speaking-animation)
- [Cara Menambah Ekspresi Baru](#cara-menambah-ekspresi-baru)

---

## Koordinat Sistem & FRTransform

Seluruh kode gambar menggunakan **ruang referensi virtual 800×600** — bukan ukuran canvas aktual. Ini memungkinkan desain bekerja di resolusi apapun tanpa hardcode pixel.

### FRTransform (fr-transform.js)

```
Canvas Aktual (misal 1920×1080)
        │
        │  FRTransform menghitung:
        │    scale = min(canvasW/800, canvasH/600)
        │    offsetX = (canvasW - 800*scale) / 2
        │    offsetY = (canvasH - 600*scale) / 2
        ▼
Ruang Virtual 800×600 (reference space)
        │
        │  tx(x)   → x * scale + offsetX      ← translate X ke canvas nyata
        │  ty(y)   → y * scale + offsetY      ← translate Y ke canvas nyata
        │  ts(size) → size * scale             ← scale ukuran (radius, width)
        ▼
Pixel Canvas Aktual
```

**Contoh Penggunaan:**
```javascript
// Di fr-eyes.js — menggambar mata kiri
const leftEyeX  = t.tx(200);  // Virtual x=200 → pixel aktual
const leftEyeY  = t.ty(220);  // Virtual y=220 → pixel aktual
const eyeW      = t.ts(130);  // Virtual w=130 → pixel aktual

ctx.ellipse(leftEyeX, leftEyeY, eyeW/2, eyeH/2, 0, 0, Math.PI*2);
```

### Layout Referensi 800×600

```
 0                    400                   800
 ┌────────────────────┬──────────────────────┐  0
 │                    │                      │
 │                    │    KABEL ROBOT        │
 │    ╱───────────────────────────────╲      │  100
 │                    │                      │
 │  ┌──────────┐      │      ┌──────────┐    │  220 ← eye_y
 │  │  MATA    │      │      │  MATA    │    │
 │  │  KIRI    │──────┼──────│  KANAN   │    │
 │  │  w:130   │      │      │  w:130   │    │
 │  │  h:160   │      │      │  h:160   │    │  380 ← eye_y + eye_h
 │  └──────────┘      │      └──────────┘    │
 │       ▲ x:200      │       x:470 ▲        │
 │                    │                      │
 │             ┌──────────────┐              │  430
 │             │    MULUT     │              │
 │             │  x:300-500   │              │  480
 │             └──────────────┘              │
 │                    │                      │
 └────────────────────┴──────────────────────┘  600
                     400

Mata Kiri Center  → (200 + 130/2) = 265, 300
Mata Kanan Center → (470       ) = 470, 300
```

---

## Render Loop & Lifecycle

```
new FaceRenderer(canvas)
        │
        │  constructor:
        │    this.state       = 'idle'
        │    this.pupilOffsetX = 0
        │    this.pupilOffsetY = 0
        │    this.speakingPhase = 0
        │    this.animationTime = 0
        │    this.blinker      = new FRBlink()
        │    this.t            = new FRTransform(canvas)
        │
        │  requestAnimationFrame(this.animate)  ← mulai loop
        ▼

animate(currentTime):
        │
        ├─① deltaTime = (currentTime - lastTime) / 1000  [detik]
        │
        ├─② updateBlink(currentTime)
        │       └── FRBlink.update(currentTime)
        │           ├── Jika blinkProgress sedang naik/turun → update progress
        │           ├── Jika progress = 1.0 dan ada nextState → swap state
        │           └── Jika belum blink → cek random timer (2-6 detik)
        │
        ├─③ updateSpeaking(deltaTime)
        │       └── Jika state = 'speaking':
        │               speakingPhase += speakingSpeed × deltaTime
        │               if speakingPhase > 2π → speakingPhase -= 2π
        │
        ├─④ animationTime += deltaTime  ← global time (untuk wave effects)
        │
        ├─⑤ ctx.fillRect(full canvas, BG_COLOR)  ← clear
        │
        ├─⑥ drawFace()
        │       ├── FRCables.drawCables(ctx, t)
        │       ├── FREyes.draw____(ctx, t, ox, oy)   ← sesuai state
        │       ├── FRBlink.drawEyelid(ctx, t)          ← overlay kelopak
        │       └── FRMouths.draw____(ctx, t)           ← sesuai state
        │
        └─⑦ requestAnimationFrame(animate)  ← loop berikutnya
```

---

## State Machine Ekspresi

```
Valid States: 'idle' | 'speaking' | 'sad' | 'shock' | 'cry' | 'shy' | 'happier'

setState('cry') dipanggil dari luar:
        │
        ├── Jika state sudah 'cry' → return (tidak ada efek)
        │
        ├── this.nextState = 'cry'
        │
        └── blinker.forceBlink('cry')
                │
                ├── blinkProgress mulai naik (0 → 1)
                │   progress += 0.20 per frame (lebih cepat dari auto-blink)
                │
                ├── Di progress = 1.0:
                │       this.state = 'cry'   ← ⚠️ STATE SWAP DISINI
                │       nextState = null
                │
                └── blinkProgress mulai turun (1 → 0)
                    progress -= 0.20 per frame
```

**Di setiap `drawFace()`, state menentukan fungsi yang dipanggil:**

```javascript
// face-renderer.js — drawFace() pseudocode
drawFace() {
    FRCables.drawCables(ctx, t);

    switch(this.state) {
        case 'cry':
            FREyes.drawCry(ctx, t, pupilOX, pupilOY, animTime);
            FRMouths.drawCry(ctx, t);
            FRCables.drawTearDrops(ctx, t, animTime);  // efek ekstra
            break;
        case 'shy':
        case 'happier':
            FREyes.drawSparkle(ctx, t, pupilOX, pupilOY);
            FRCables.drawBlush(ctx, t);  // blush ekstra
            if (state==='shy') FRMouths.drawShy(ctx, t);
            else               FRMouths.drawHappier(ctx, t);
            break;
        // ... dst
    }
    
    FRBlink.drawEyelid(ctx, t);  // selalu paling atas (overlay)
}
```

---

## Blink-Swap Algorithm

### Timeline Visual

```
Time ──────────────────────────────────────────────────────────▶

Phase:   OPEN     │ CLOSING  │ PEAK  │ OPENING   │ OPEN
                  │          │       │           │
progress: 0.0 ───▶│──────── 1.0 ────│──────────▶│ 0.0
                  │          │       │           │
                  │          ├──────→ STATE SWAP  │
                  │          │   (di progress=1.0)│

speed:   auto     │  0.08/f  │       │  0.08/f   │
         blink    │  0.20/f  │       │  0.20/f   │ (jika force)

Duration (60fps): ─── ~12 frames ─── | ─── ~12 frames ───
```

### FRBlink — Fungsi Kunci

```javascript
// fr-blink.js

class FRBlink {

    // Dipanggil setiap frame dari animate()
    update(currentTime) {
        if (blinkProgress > 0 || isBlinking) {
            // Naikkan progress saat closing
            if (closing) {
                blinkProgress += speed;  // speed = 0.08 atau 0.20
                if (blinkProgress >= 1.0) {
                    blinkProgress = 1.0;
                    // ⚠️ SWAP STATE DISINI
                    if (this.nextState) {
                        renderer.state = this.nextState;
                        this.nextState = null;
                    }
                    closing = false;  // mulai opening
                }
            } else {
                // Turunkan progress saat opening
                blinkProgress -= speed;
                if (blinkProgress <= 0) {
                    blinkProgress = 0;
                    isBlinking = false;
                }
            }
        } else {
            // Idle — tunggu random timer
            if (currentTime > nextBlinkTime) {
                this.startBlink(null, speed=0.08);
                nextBlinkTime = currentTime + random(2000, 6000);
            }
        }
    }

    // Dipanggil saat ekspresi berubah
    forceBlink(nextState) {
        this.nextState = nextState;
        this.startBlink(nextState, speed=0.20);  // lebih cepat
    }

    // Dipanggil setiap frame dari drawFace()
    drawEyelid(ctx, t) {
        if (blinkProgress <= 0) return;
        const lidH = eyeHeight * blinkProgress;
        ctx.fillRect(eyeX, eyeY, eyeW, lidH);    // tutup dari atas
        ctx.strokeRect(eyeX, eyeY + lidH, eyeW, 4);  // garis hitam di bawah kelopak
    }
}
```

---

## Menggambar Mata (fr-eyes.js)

### Mata Default (`drawDefault`)

```
Langkah-langkah per mata:

1. Outline Hitam (ellipse lebih besar)
   ctx.ellipse(cx, cy, (w/2)+6, (h/2)+6, ...)  ← black outline

2. Gradient Fill (ungu gelap → hitam)
   LinearGradient: top=(80,70,150) → bottom=(0,0,0)
   Clip ke ellipse mata, fill gradient

3. Glint Utama (highlight putih)
   cx + (w*0.3) + pupilOffsetX   ← bergerak dengan pupil
   cy + (h*0.25) + pupilOffsetY
   radius = w * 0.18
   warna: white

4. Glint Kecil (aksen)
   cx - 5, cy + (h*0.3)
   radius = w * 0.05

5. Clip Release
   ctx.restore()
```

```
Tampilan mata (skematik):

   ╭──────────────────────────────╮  ← outline hitam
   │░░░░░░░░░░░░░░░░░░░░░░░░░░░░│
   │░░░░░░░ ○ ░░░░░░░░░░░░░░░░░│  ← glint besar (○)
   │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│
   │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│  ← gradient tengah
   │████████████████████████████│
   │█████████ · ████████████████│  ← glint kecil (·)
   ╰──────────────────────────────╯  ← clip boundary
```

### Mata Sparkle (`drawSparkle`) — untuk `shy` & `happier`

Sama seperti default, tapi glint diganti **bintang 8 titik** (⭐):

```javascript
// Menggambar bintang 8 titik
function drawStar(ctx, cx, cy, size) {
    const half  = size / 2;
    const inner = size / 5;
    const points = [
        [cx,       cy - half],  // atas
        [cx+inner, cy - inner], // kanan-atas
        [cx+half,  cy],         // kanan
        [cx+inner, cy + inner], // kanan-bawah
        [cx,       cy + half],  // bawah
        [cx-inner, cy + inner], // kiri-bawah
        [cx-half,  cy],         // kiri
        [cx-inner, cy - inner], // kiri-atas
    ];
    ctx.beginPath();
    ctx.moveTo(...points[0]);
    points.slice(1).forEach(p => ctx.lineTo(...p));
    ctx.closePath();
    ctx.fill();
}
```

### Mata Cry (`drawCry`) — Water Wave Effect

```
Water Wave menggunakan Sin Wave:

  Iterasi setiap x dari eyeLeft ke eyeRight (step 2px):

    y = baseY + amplitude × sin(freq × x + animTime × speed)

    di mana:
      baseY      = titik tengah bawah mata (waterLevel)
      amplitude  = 4  (tinggi gelombang)
      freq       = 0.15
      speed      = 3  (× animTime untuk animasi)

Visualisasi gelombang:
    ┌────────────────────────────────────┐
    │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│  ← area "air" (biru transparan)
    │∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿│  ← wave line
    │██████████████████████████████████│  ← area bawah (solid blue)
    └────────────────────────────────────┘

Ditambah: Tetesan air mata (tear drops)
    Posisi: bawah setiap mata
    Shape: ellipse kecil (8×12px)
    Animasi: jatuh ke bawah berdasarkan animTime
```

---

## Menggambar Mulut (fr-mouths.js)

### Mulut Idle / Default (Senyum)

```
Kurva Bezier senyum (smile curve):

  P1 ────────── C1
  │                 ╲
  │                   C2 ────── P2
  │
  Control points mengangkat sudut ke atas → tampak senyum

  P1  = (300, 470)  ← sudut kiri mulut
  P2  = (500, 470)  ← sudut kanan mulut
  C1  = (330, 440)  ← kurva kiri-atas
  C2  = (470, 440)  ← kurva kanan-atas
  
  Lidah: Ellipse kecil di dalam rongga mulut
    fill = (220, 100, 80)  ← merah-oranye
    offset: turun dari pusat mulut

ctx.bezierCurveTo(C1x, C1y, C2x, C2y, P2x, P2y)
```

### Mulut Speaking (Oscillating Oval)

```
Speaking menggunakan phase oscillation:

  mouthHeight = baseH + amplitude × sin(speakingPhase)

  di mana:
    baseH      = 30  (tinggi minimum mulut)
    amplitude  = 25  (tinggi maksimum tambahan)
    speakingPhase += 4 × deltaTime  (rad/detik)

Timeline oscillation (satu siklus):
  phase=0  → mulut baseH (30px)     = "tertutup"
  phase=π/2→ mulut baseH+amp (55px) = "terbuka penuh"
  phase=π  → mulut baseH (30px)     = "tertutup"
  phase=3π/2→ mulut baseH+amp       = "terbuka penuh"
  phase=2π → (reset)

Tampilan:
  Tertutup:  ╭────────╮
  Terbuka:   ╭────────╮
             │        │
             │        │
             ╰────────╯
```

### Mulut Sad (Frown)

```
Frown = senyum terbalik

  Bezier control points dibalik ke bawah:
  P1  = (300, 460)
  P2  = (500, 460)
  C1  = (330, 490)  ← control turun = melengkung ke bawah
  C2  = (470, 490)

Tampilan: ╭────────────╮
               ╲      ╱
                ╲────╱
```

### Mulut Shock (O-Shape Besar)

```
Ellipse besar di tengah wajah:

  cx = 400  (center horizontal)
  cy = 470  (vertical)
  rx = 50   (lebar)
  ry = 60   (tinggi, lebih besar → mulut terbuka)

  Rongga: fill dark (#282828)
  Outline: fill hitam, lebih besar 8px

Tampilan:
    ╭──────────────╮
    │              │
    │    (gelap)   │
    │              │
    │              │
    ╰──────────────╯
```

### Mulut Shy (Double Half-Circle / ω shape)

```
Dua setengah lingkaran kecil → membentuk huruf ω

  Lingkaran kiri:
    arc(cx-20, cy, 18, 0, Math.PI)   ← setengah lingkaran ke bawah
    
  Lingkaran kanan:
    arc(cx+20, cy, 18, 0, Math.PI)   ← setengah lingkaran ke bawah

  Tampilan: ω
```

---

## Kabel, Blush & Bintang (fr-cables.js)

### Kabel Robot

```
Kabel kiri: dari pojok kiri atas layar → atas mata kiri → sisi atas mata kiri

  Lines: [(-10, 50), (eyeL.cx, eyeL.top - 50), (eyeL.cx, eyeL.top)]

Kabel kanan: dari pojok kanan atas layar → atas mata kanan → sisi atas mata kanan

  Lines: [(810, 50), (eyeR.cx, eyeR.top - 50), (eyeR.cx, eyeR.top)]

Kabel tengah: V-shape antara dua mata

  Lines: [(eyeL.right, eyeL.cy), (400, eyeL.cy+30), (eyeR.left, eyeR.cy)]

  Diagram:
  
  ╱─────────────────────────────────────────╲
  │           │                   │          │
  │     ╭─────┴────╮         ╭────┴─────╮   │
  │     │  MATA L  │─────────│  MATA R  │   │
  │     ╰──────────╯         ╰──────────╯   │
```

### Blush (Pipi Merah)

```
Dua ellipse merah muda transparan di sisi luar mata:

  Pipi kiri:
    ellipse(eyeL.cx - 80, eyeL.bottom + 20, 50, 30)
    fill = rgba(255, 150, 160, 0.5)

  Pipi kanan:
    ellipse(eyeR.cx + 80, eyeR.bottom + 20, 50, 30)
    fill = rgba(255, 150, 160, 0.5)

Digunakan di: shy, happier
```

---

## Pupil Offset & Constraint System

Pupil bergerak mengikuti gaze data dari FaceTracker atau FER gaze. Ada tiga lapis proteksi agar pupil tidak keluar dari bola mata:

```
Layer 1: Input Clamping (face-tracker.js)
─────────────────────────────────────────
  rawGazeX = MediaPipe result
  gazeX = Math.max(-1, Math.min(1, rawGazeX))
  
  Nilai gaze SELALU dalam [-1, 1]


Layer 2: Pixel Shift Limit (face-renderer.js)
──────────────────────────────────────────────
  MAX_SHIFT_X = 20  (pixel, dalam virtual 800×600 space)
  MAX_SHIFT_Y = 22
  
  shiftX = gazeX × MAX_SHIFT_X  →  range [-20, +20]
  shiftY = gazeY × MAX_SHIFT_Y  →  range [-22, +22]


Layer 3: Canvas Clip Region (fr-eyes.js)
──────────────────────────────────────────
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(eyeCx, eyeCy, eyeW/2, eyeH/2, 0, 0, 2*Math.PI);
  ctx.clip();
  
  // Semua draw di sini di-clip ke dalam ellipse
  drawGlint(cx + shiftX, cy + shiftY);  ← aman, terpotong jika keluar
  
  ctx.restore();


Visualisasi:

  ╭──────────────────────────╮
  │                          │
  │  ○ ← glint (bisa gerak  │  Jika shiftX terlalu besar:
  │         dalam area ini)  │  glint akan terpotong di tepi
  │                          │
  ╰──────────────────────────╯
  ▲                          ▲
  clip boundary             clip boundary
```

---

## Speaking Animation

```
Lifecycle Speaking:

app.js: startSpeaking(duration):
    │
    ├── clearTimeout(speakingTimer)
    │
    ├── faceRenderer.startSpeaking()
    │       └── this.state = 'speaking'
    │           this.speakingPhase = 0
    │
    └── speakingTimer = setTimeout(() => {
            faceRenderer.stopSpeaking()
                └── this.state = 'idle'
        }, duration × 1000)


Setiap frame saat state='speaking':

  updateSpeaking(deltaTime):
      speakingPhase += 4 × deltaTime    ← 4 rad/detik ≈ 0.64 Hz

  drawFace():
      FRMouths.drawSpeaking(ctx, t, this.speakingPhase)
          │
          └── mouthH = 30 + 25 × Math.sin(speakingPhase)
              ctx.ellipse(..., mouthW/2, mouthH/2, ...)
```

---

## Cara Menambah Ekspresi Baru

Langkah-langkah menambahkan ekspresi `'angry'`:

### Step 1: Tambahkan mulut di `fr-mouths.js`

```javascript
// fr-mouths.js
const FRMouths = {
    // ... existing ...

    drawAngry(ctx, t) {
        // Mulut garis tebal (clenched teeth / frowning line)
        ctx.beginPath();
        ctx.moveTo(t.tx(310), t.ty(465));
        // Zigzag atau flat line tebal
        ctx.lineTo(t.tx(490), t.ty(465));
        ctx.lineWidth = t.ts(8);
        ctx.strokeStyle = '#1a1a1a';
        ctx.stroke();
    }
};
```

### Step 2: Tambahkan mata di `fr-eyes.js` (opsional jika pakai default)

```javascript
// Atau gunakan drawDefault yang sudah ada
// Untuk mata khusus marah (alis turun):
drawAngry(ctx, t, ox, oy) {
    this.drawDefault(ctx, t, ox, oy);
    // Tambah alis miring (garis di atas mata)
    ctx.beginPath();
    ctx.moveTo(t.tx(180), t.ty(200));
    ctx.lineTo(t.tx(330), t.ty(215));  // alis kiri turun ke tengah
    ctx.lineWidth = t.ts(8);
    ctx.stroke();
    // ... kanan
}
```

### Step 3: Daftarkan di `face-renderer.js` `drawFace()`

```javascript
// face-renderer.js — drawFace()
case 'angry':
    FREyes.drawAngry(ctx, t, pupilOX, pupilOY);
    FRMouths.drawAngry(ctx, t);
    break;
```

### Step 4: Daftarkan di `app.js` expression handler

```javascript
// app.js — handleExpressionMessage()
const VALID_EXPRESSIONS = ['idle','speaking','sad','shock','cry','shy','happier','angry'];
// pastikan 'angry' ada di list
```

### Step 5: Tambahkan mapping di FER Publisher (opsional)

```python
# publisher_brone.py
EMOTION_TO_EXPRESSION = {
    'Upset': 'angry',  # sebelumnya 'cry'
}
```

---

← [01 · Arsitektur](01-architecture.md) | [03 · Gaze Tracking →](03-gaze-tracking.md)
