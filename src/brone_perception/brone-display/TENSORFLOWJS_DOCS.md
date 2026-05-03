# Dokumentasi TensorFlow.js — Robot Expression Display

Dokumen ini menjelaskan secara lengkap bagaimana TensorFlow.js dan BlazeFace digunakan dalam proyek ini untuk mendeteksi wajah pengguna secara real-time melalui webcam, kemudian menggerakkan pupil robot agar mengikuti posisi wajah tersebut.

---

## 1. Library yang Digunakan

Dimuat secara langsung via CDN di `index.html`:

```html
<!-- TensorFlow.js Core — engine inferensi ML di browser -->
<script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.17.0/dist/tf.min.js"></script>

<!-- BlazeFace — model pre-trained untuk deteksi wajah -->
<script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/blazeface@0.1.0/dist/blazeface.js"></script>
```

| Library | Versi | Fungsi |
|---|---|---|
| `@tensorflow/tfjs` | 4.17.0 | Engine utama: menjalankan tensor operations dan inferensi model menggunakan WebGL backend |
| `@tensorflow-models/blazeface` | 0.1.0 | Model pre-trained: mendeteksi bounding box wajah dari frame video |

Kedua library ini berjalan **sepenuhnya di browser** — tidak ada data video yang dikirim ke server.

---

## 2. Arsitektur & Alur Data

```
Webcam (getUserMedia)
        │
        ▼
┌───────────────────┐
│   face-tracker.js │  ← Satu-satunya file yang menggunakan TF.js secara langsung
│                   │
│  blazeface model  │  estimateFaces(videoEl) setiap 100ms
│  ─────────────── │
│  Output: gaze     │  smoothGazeX, smoothGazeY (-1 sampai 1)
└────────┬──────────┘
         │ getGaze()
         ▼
┌───────────────────┐
│     app.js        │  Head pan logic + kompensasi sudut kepala
└────────┬──────────┘
         │ setPupilOffset(x, y)
         ▼
┌───────────────────┐
│  face-renderer.js │  Canvas drawing — pupil robot bergerak
└───────────────────┘
         │
         ▼ (jika pupil mencapai batas edge)
┌───────────────────┐
│  mqtt-client.js   │  Publish robot/head_control ke robot fisik
└───────────────────┘
```

---

## 3. Penjelasan Kode: `face-tracker.js`

File ini adalah inti dari seluruh operasi TensorFlow.js.

### 3.1 Konstruktor & State

```javascript
class FaceTracker {
    constructor(videoElement) {
        this.video = videoElement;       // Elemen <video> yang menampung stream webcam
        this.isRunning = false;
        this.isInitialized = false;

        // Output gaze mentah
        this.gazeX = 0;                 // Nilai -1 (kiri) sampai 1 (kanan)
        this.gazeY = 0;                 // Nilai -1 (atas) sampai 1 (bawah)

        // Output gaze yang sudah diperhalus
        this.smoothGazeX = 0;
        this.smoothGazeY = 0;

        // Smoothing factor: 0 = tidak diperhalus, 1 = tidak bergerak
        this.smoothingFactor = 0.65;

        // Dead zone: gerakan kecil di sekitar pusat diabaikan
        this.deadZone = 0.04;

        // Referensi ke BlazeFace model
        this.model = null;

        this.faceDetected = false;

        // Interval deteksi — sengaja dibatasi ~10fps untuk hemat performa
        this.detectInterval = 100; // ms
        this.detectTimer = null;
    }
}
```

**Catatan desain:**
- `smoothingFactor = 0.65` dipilih agar gerakan pupil terasa natural dan tidak terlalu tiba-tiba.
- `deadZone = 0.04` mencegah pupil bergetar saat pengguna diam.
- `detectInterval = 100ms` sengaja lebih lambat dari framerate rendering (60fps) karena inferensi ML lebih mahal secara komputasi.

---

### 3.2 Inisialisasi (`init()`)

```javascript
async init() {
    try {
        // LANGKAH 1: Minta akses kamera dari browser
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 320 },   // Resolusi kecil → inferensi lebih cepat
                height: { ideal: 240 },
                facingMode: 'user'        // Kamera depan
            },
            audio: false
        });

        // Sambungkan stream ke elemen <video> yang tersembunyi di HTML
        this.video.srcObject = stream;

        // Tunggu video siap diputar
        await new Promise((resolve) => {
            this.video.onloadedmetadata = () => {
                this.video.play();
                resolve();
            };
        });

        // LANGKAH 2: Muat model BlazeFace
        // Ini akan mengunduh weight model (~1MB) dari CDN jsDelivr
        this.model = await blazeface.load();

        // LANGKAH 3: Mulai loop deteksi
        this.isInitialized = true;
        this.isRunning = true;
        this.startDetectionLoop();

        return true;

    } catch (error) {
        // Biasanya terjadi jika pengguna menolak izin kamera
        console.error('FaceTracker init failed:', error.name, error.message);
        this.isInitialized = false;
        return false;
    }
}
```

**Dua operasi async utama:**
1. `getUserMedia()` — meminta izin kamera ke browser (memerlukan HTTPS atau localhost)
2. `blazeface.load()` — download & compile model ke WebGL, biasanya 1–3 detik pertama kali

---

### 3.3 Loop Deteksi (`startDetectionLoop` & `detect`)

```javascript
startDetectionLoop() {
    // Gunakan setInterval agar deteksi berjalan di rate yang konsisten
    // (bukan requestAnimationFrame, karena kita tidak butuh 60fps untuk ML)
    this.detectTimer = setInterval(() => {
        if (this.isRunning) {
            this.detect();
        }
    }, this.detectInterval); // Setiap 100ms

    // Langsung jalankan sekali tanpa menunggu interval pertama
    this.detect();
}

async detect() {
    if (!this.isRunning || !this.model) return;
    if (this.video.readyState < 2) return; // Video belum siap (readyState 2 = HAVE_CURRENT_DATA)

    try {
        // ─── INI INTI TENSORFLOW.JS ───
        // estimateFaces() mengambil frame saat ini dari elemen <video>,
        // menjalankan inferensi model BlazeFace, dan mengembalikan deteksi.
        //
        // Parameter kedua (false) = returnTensors: false
        // Artinya output berupa array JavaScript biasa, bukan Tensor TF.js.
        // Ini lebih mudah digunakan tapi sedikit lebih lambat karena ada konversi.
        const predictions = await this.model.estimateFaces(this.video, false);

        if (predictions.length > 0) {
            // Ambil deteksi pertama (wajah paling confident)
            const face = predictions[0];

            // BlazeFace output:
            // face.topLeft     → [x, y] pojok kiri atas bounding box
            // face.bottomRight → [x, y] pojok kanan bawah bounding box
            // face.landmarks   → [[x,y], ...] 6 titik landmark (tidak dipakai di sini)
            // face.probability → confidence score (0–1)

            const topLeft = face.topLeft;
            const bottomRight = face.bottomRight;

            // Hitung titik tengah wajah dalam koordinat pixel
            const faceCenterX = (topLeft[0] + bottomRight[0]) / 2;
            const faceCenterY = (topLeft[1] + bottomRight[1]) / 2;

            // Normalisasi ke range 0..1 relatif terhadap lebar/tinggi video
            const normX = faceCenterX / this.video.videoWidth;
            const normY = faceCenterY / this.video.videoHeight;

            this.faceDetected = true;

            // Konversi ke range -1..1 (tengah frame = 0,0)
            // X di-mirror agar terasa natural dari sudut pandang pengguna:
            // pengguna gerak ke kiri → pupil robot lihat ke kiri
            let rawX = -(normX - 0.5) * 2;  // Mirror: (0.5 - normX) * 2
            let rawY =  (normY - 0.5) * 2;

            // Terapkan dead zone: abaikan gerakan sangat kecil di sekitar pusat
            if (Math.abs(rawX) < this.deadZone) rawX = 0;
            if (Math.abs(rawY) < this.deadZone) rawY = 0;

            // Clamp ke batas -1..1
            rawX = Math.max(-1, Math.min(1, rawX));
            rawY = Math.max(-1, Math.min(1, rawY));

            this.gazeX = rawX;
            this.gazeY = rawY;

        } else {
            this.faceDetected = false;

            // Tidak ada wajah → perlahan balik ke tengah (lerp ke 0)
            this.gazeX *= 0.92;
            this.gazeY *= 0.92;

            // Snap ke 0 saat sudah sangat dekat
            if (Math.abs(this.gazeX) < 0.01) this.gazeX = 0;
            if (Math.abs(this.gazeY) < 0.01) this.gazeY = 0;
        }

        // ─── SMOOTHING (Exponential Moving Average) ───
        // Formula: newSmooth = smooth * factor + raw * (1 - factor)
        // factor = 0.65 → bobot 65% nilai lama, 35% nilai baru
        // Efek: gerakan diperhalus, mengurangi noise dari deteksi yang tidak stabil
        this.smoothGazeX = this.smoothGazeX * this.smoothingFactor + this.gazeX * (1 - this.smoothingFactor);
        this.smoothGazeY = this.smoothGazeY * this.smoothingFactor + this.gazeY * (1 - this.smoothingFactor);

    } catch (error) {
        // Abaikan error deteksi secara senyap (bisa terjadi jika frame tidak valid)
    }
}
```

---

### 3.4 Output (`getGaze`)

```javascript
// Dipanggil oleh app.js setiap frame (requestAnimationFrame ~60fps)
getGaze() {
    return {
        x: this.smoothGazeX,   // -1 (kiri) sampai 1 (kanan)
        y: this.smoothGazeY    // -1 (atas) sampai 1 (bawah)
    };
}
```

---

## 4. Integrasi di `app.js`

`app.js` mengonsumsi output dari `FaceTracker` dan menerapkan logika bisnis tambahan sebelum data dikirim ke renderer.

### 4.1 Inisialisasi FaceTracker

```javascript
async initFaceTracker() {
    const videoEl = document.getElementById('webcamVideo');
    this.faceTracker = new FaceTracker(videoEl);

    // init() mengembalikan true jika kamera & model berhasil dimuat
    const success = await this.faceTracker.init();

    if (success) {
        this.startTrackingLoop(); // Mulai loop render
    }
}
```

### 4.2 Tracking Loop & Head Pan Logic

```javascript
startTrackingLoop() {
    const updateTracking = () => {
        if (this.faceTracker && this.faceTracker.isRunning && this.trackingEnabled) {
            const gaze = this.faceTracker.getGaze();  // Ambil output TF.js

            // ─── HEAD PAN LOGIC ───
            // Jika pupil sudah terlalu dekat ke tepi (threshold: 70% dari batas),
            // kirimkan perintah ke robot untuk memutar kepalanya.
            if (Math.abs(gaze.x) > this.PUPIL_EDGE_THRESHOLD) {       // 0.70
                const now = Date.now();
                if (now - this.lastHeadCommandTime > this.HEAD_COMMAND_INTERVAL) { // 300ms
                    const direction = gaze.x > 0 ? 1 : -1;
                    this.panHead(direction * this.HEAD_PAN_STEP, 'pupil_edge'); // 15 derajat
                    this.lastHeadCommandTime = now;
                }
            }

            // ─── KOMPENSASI VIRTUAL ───
            // Setelah kepala robot berputar, gaze X dikurangi kontribusi sudut kepala
            // agar pupil tampak kembali ke tengah (seperti mata manusia saat kepala bergerak)
            const headCompensation = -(this.headAngle / this.HEAD_MAX_ANGLE); // -1..1
            const compensatedGazeX = Math.max(-1, Math.min(1, gaze.x + headCompensation));

            // Kirim ke canvas renderer
            this.faceRenderer.setPupilOffset(compensatedGazeX, gaze.y);
        }

        requestAnimationFrame(updateTracking); // Loop di ~60fps
    };

    requestAnimationFrame(updateTracking);
}
```

**Perbedaan penting antara dua loop:**

| Loop | Dijalankan di | Frekuensi | Tugas |
|---|---|---|---|
| `setInterval` (FaceTracker) | `face-tracker.js` | ~10fps (100ms) | Inferensi ML — deteksi wajah |
| `requestAnimationFrame` (App) | `app.js` | ~60fps | Membaca gaze & update canvas |

Pemisahan ini penting: inferensi ML berjalan lambat (10fps) tapi rendering tetap mulus (60fps).

---

## 5. Penjelasan Output BlazeFace

Satu elemen `predictions[0]` dari `model.estimateFaces()` memiliki struktur:

```javascript
{
    topLeft: [x, y],          // Pixel, pojok kiri atas bounding box wajah
    bottomRight: [x, y],      // Pixel, pojok kanan bawah bounding box wajah
    landmarks: [              // 6 titik landmark wajah dalam pixel
        [x, y],               // 0: mata kanan
        [x, y],               // 1: mata kiri
        [x, y],               // 2: hidung
        [x, y],               // 3: mulut
        [x, y],               // 4: telinga kanan
        [x, y]                // 5: telinga kiri
    ],
    probability: [0.998]      // Confidence score — semakin dekat 1 semakin yakin
}
```

> **Catatan:** `landmarks` tersedia di output BlazeFace tapi tidak dimanfaatkan di proyek ini.
> Saat ini hanya `topLeft` dan `bottomRight` yang dipakai untuk menghitung pusat wajah.
> Untuk pengembangan ke depan, `landmarks[0]` & `landmarks[1]` (posisi mata) bisa digunakan
> untuk tracking yang lebih presisi.

---

## 6. Parameter Konfigurasi

Semua parameter kunci ada di konstruktor `FaceTracker` dan `ExpressionApp`:

| Parameter | Lokasi | Nilai Default | Efek jika Dinaikkan |
|---|---|---|---|
| `smoothingFactor` | `FaceTracker` | `0.65` | Gerakan makin mulus tapi makin lambat merespons |
| `deadZone` | `FaceTracker` | `0.04` | Area diam di tengah makin besar → lebih stabil |
| `detectInterval` | `FaceTracker` | `100ms` | Deteksi makin jarang → hemat CPU, respons lebih lambat |
| `PUPIL_EDGE_THRESHOLD` | `ExpressionApp` | `0.70` | Batas lebih tinggi → kepala robot lebih jarang berputar |
| `HEAD_PAN_STEP` | `ExpressionApp` | `15°` | Kepala berputar lebih besar setiap trigger |
| `HEAD_COMMAND_INTERVAL` | `ExpressionApp` | `300ms` | Rate limit — perintah pan tidak terlalu sering |

---

## 7. Mengapa BlazeFace?

BlazeFace dipilih karena beberapa alasan:

- **Ringan & cepat** — model ~1MB, dioptimalkan untuk perangkat mobile dan browser
- **WebGL backend** — TF.js secara otomatis menggunakan GPU (via WebGL) untuk akselerasi
- **Tanpa server** — inferensi 100% di browser, privasi terjaga, tidak perlu koneksi ke backend ML
- **Pre-trained** — tidak memerlukan training khusus, langsung bisa digunakan
- **Cukup untuk kebutuhan** — tracking posisi kepala hanya butuh bounding box, tidak perlu landmark detail seperti MediaPipe Face Mesh

---

## 8. Pertimbangan Performa

- **Resolusi video `320×240`** — sengaja kecil. BlazeFace akan me-resize input secara internal ke `128×128` sebelum inferensi, sehingga resolusi tinggi tidak menambah akurasi, hanya menambah overhead konversi.
- **`returnTensors: false`** di `estimateFaces(video, false)` — output dikembalikan sebagai array JS biasa, memudahkan penggunaan tapi ada sedikit overhead konversi dari Tensor. Untuk performa maksimal bisa diubah ke `true` dan hasilnya diproses sebagai Tensor.
- **Loop terpisah** — ML loop (10fps) dan render loop (60fps) dipisah agar animasi tetap mulus meski inferensi sedang berlangsung.
