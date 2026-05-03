/**
 * face-renderer.js  (Slim Orchestrator)
 * ======================================
 * FaceRenderer hanya bertugas:
 *   1. Mengelola state animasi (idle, speaking, sad, dll.)
 *   2. Menjalankan animation loop
 *   3. Men-dispatch panggilan ke sub-module feature:
 *        FRTransform  → transform helpers (tx, ty, ts)
 *        FRBlink      → BlinkController (FSM kedip)
 *        FRCables     → drawCables, drawBlush, drawStar
 *        FREyes       → drawEyeGradient, drawEyelid, drawPurpleEyeWithWave, dll.
 *        FRMouths     → drawHappyMouth, drawSpeakingMouth, dll.
 *
 * Semua logika gambar yang spesifik ekspresi ada di file renderers/*.js.
 *
 * Dependencies (harus dimuat via <script> sebelum file ini):
 *   js/renderers/fr-transform.js
 *   js/renderers/fr-blink.js
 *   js/renderers/fr-cables.js
 *   js/renderers/fr-eyes.js
 *   js/renderers/fr-mouths.js
 */

class FaceRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx    = canvas.getContext('2d');

        // ── State ──────────────────────────────────────────────────────────
        this.state         = 'standby';
        this.nextState     = null;
        this.speakingPhase = 0;
        this.speakingSpeed = 4;       // Oscillasi per detik
        this.animationTime = 0;       // Waktu kontinu untuk animasi fluid

        // ── Pupil tracking offset (-1 to 1) ───────────────────────────────
        this.pupilOffsetX   = 0;
        this.pupilOffsetY   = 0;
        this.MAX_PUPIL_SHIFT_X = 20;
        this.MAX_PUPIL_SHIFT_Y = 22;

        // ── Blink controller ───────────────────────────────────────────────
        this.blinker = new FRBlink.BlinkController();

        // ── Transform (dihitung ulang saat resize) ─────────────────────────
        this.t = FRTransform.create(canvas.width, canvas.height);

        // ── Setup canvas & animation loop ─────────────────────────────────
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.lastTime = performance.now();
        this.animate();
    }

    // ── Resize ─────────────────────────────────────────────────────────────
    resize() {
        this.canvas.width  = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.t = FRTransform.create(this.canvas.width, this.canvas.height);
    }

    // ── Animation Loop ─────────────────────────────────────────────────────
    animate(currentTime = performance.now()) {
        const dt = (currentTime - this.lastTime) / 1000;
        this.lastTime = currentTime;

        // Update blink FSM
        this.blinker.update(currentTime, this.nextState);

        // Swap state ketika mata tertutup penuh
        if (this.blinker.progress >= 1.0 && this.nextState && this.nextState !== this.state) {
            this.state     = this.nextState;
            this.nextState = null;
        }

        // Update speaking phase
        if (this.state === 'speaking') {
            this.speakingPhase += dt * this.speakingSpeed * Math.PI * 2;
        }

        this.animationTime += dt;

        this._clear();
        this._drawFace();

        requestAnimationFrame((t) => this.animate(t));
    }

    // ── Clear canvas ───────────────────────────────────────────────────────
    _clear() {
        this.ctx.fillStyle = this.state === 'standby' ? '#000000' : 'rgb(205, 215, 225)';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    // ── Draw Face (dispatcher) ─────────────────────────────────────────────
    _drawFace() {
       if (this.state === 'standby') return;

        const t       = this.t;
        const ctx     = this.ctx;
        const centerX = 400;   // Reference center

        // Eye rectangles (reference coordinates, 800×600 space)
        const eyeY    = 220;
        const eyeW    = 110;
        const eyeH    = 150;
        const dist    = 140;

        const leftEye = {
            x: centerX - dist - eyeW, y: eyeY, width: eyeW, height: eyeH,
            centerX: centerX - dist - eyeW / 2,
            centerY: eyeY + eyeH / 2,
        };
        const rightEye = {
            x: centerX + dist, y: eyeY, width: eyeW, height: eyeH,
            centerX: centerX + dist + eyeW / 2,
            centerY: eyeY + eyeH / 2,
        };

        const pox = this.pupilOffsetX;
        const poy = this.pupilOffsetY;
        const msx = this.MAX_PUPIL_SHIFT_X;
        const msy = this.MAX_PUPIL_SHIFT_Y;

        // 1. Kabel robot
        FRCables.drawCables(ctx, t, leftEye, rightEye, centerX);

        // 2. Blush (hanya untuk shy / happier)
        if (this.state === 'shy' || this.state === 'happier') {
            FRCables.drawBlush(ctx, t, leftEye);
            FRCables.drawBlush(ctx, t, rightEye);
        }

        // 3. Mata (crying menggunakan wave eye + tear stream)
        if (this.state === 'cry') {
            FREyes.drawCartoonStream(ctx, t, leftEye.centerX,  leftEye.y  + leftEye.height  + 20, this.animationTime);
            FREyes.drawCartoonStream(ctx, t, rightEye.centerX, rightEye.y + rightEye.height + 20, this.animationTime);
            FREyes.drawPurpleEyeWithWave(ctx, t, leftEye,  this.animationTime,     pox, poy, msx, msy);
            FREyes.drawPurpleEyeWithWave(ctx, t, rightEye, this.animationTime + 2, pox, poy, msx, msy);
        } else if (this.state === 'shy' || this.state === 'happier') {
            FREyes.drawEyeGradientSparkles(ctx, t, leftEye,  pox, poy, msx, msy);
            FREyes.drawEyeGradientSparkles(ctx, t, rightEye, pox, poy, msx, msy);
        } else {
            FREyes.drawEyeGradient(ctx, t, leftEye,  pox, poy, msx, msy);
            FREyes.drawEyeGradient(ctx, t, rightEye, pox, poy, msx, msy);
        }

        // 4. Kelopak mata (blink)
        FREyes.drawEyelid(ctx, t, leftEye,  this.blinker.progress);
        FREyes.drawEyelid(ctx, t, rightEye, this.blinker.progress);

        // 5. Mulut (dispatch berdasarkan state)
        switch (this.state) {
            case 'speaking':
                FRMouths.drawSpeakingMouth(ctx, t, centerX, this.speakingPhase);
                break;
            case 'sad':
                FRMouths.drawSadMouth(ctx, t, centerX);
                break;
            case 'shock':
                FRMouths.drawShockMouth(ctx, t, centerX, this.blinker.progress);
                break;
            case 'cry':
                FRMouths.drawCryMouth(ctx, t, centerX);
                break;
            case 'shy':
                FRMouths.drawShyMouth(ctx, t, centerX);
                break;
            case 'happier':
            case 'idle':
            default:
                FRMouths.drawHappyMouth(ctx, t, centerX);
                break;
        }
    }

    // ── Public API ──────────────────────────────────────────────────────────

    /** Mulai animasi bicara dengan transisi blink. */
    startSpeaking() {
        if (this.state !== 'speaking') this.blinker.forceBlink();
        this.nextState     = 'speaking';
        this.speakingPhase = 0;
        console.log('[FaceRenderer] startSpeaking');
    }

    /** Stop bicara → kembali ke idle. */
    stopSpeaking() {
        if (this.state === 'speaking') this.setState('idle');
        console.log('[FaceRenderer] stopSpeaking');
    }

    /**
     * Set ekspresi baru. Transisi dilakukan lewat kedip agar halus.
     * @param {string} state - 'idle' | 'speaking' | 'sad' | 'shock' | 'cry' | 'shy' | 'happier'
     */
    setState(state) {
        if (state === 'speaking') { this.startSpeaking(); return; }
        if (this.state !== state) {
            this.blinker.forceBlink();
            this.nextState = state;
        }
        console.log('[FaceRenderer] setState →', state);
    }

    /**
     * Set offset pupil untuk gaze tracking.
     * @param {number} x - -1..1 (kiri → kanan)
     * @param {number} y - -1..1 (atas → bawah)
     */
    setPupilOffset(x, y) {
        this.pupilOffsetX = Math.max(-1, Math.min(1, x));
        this.pupilOffsetY = Math.max(-1, Math.min(1, y));
    }
}

window.FaceRenderer = FaceRenderer;
