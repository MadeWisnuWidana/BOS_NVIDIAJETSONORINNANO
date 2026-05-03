/**
 * Face Tracker - MediaPipe Face Detection for pupil tracking
 * Features:
 *   - MediaPipe Face Detection (lightweight 'short' model)
 *   - Mouse/touch fallback when camera is denied
 *   - Debug overlay: status badge + mini webcam preview with bounding-box
 *   - Exposes smoothed gaze (getGaze()) compatible with the existing FaceRenderer
 */

class FaceTracker {
    constructor(videoElement) {
        this.video = videoElement;          // hidden main video (for MediaPipe)
        this.isRunning = false;
        this.isInitialized = false;

        // Normalized gaze output (-1 to 1)
        this.gazeX = 0;
        this.gazeY = 0;

        // Smoothed values (exposed via getGaze())
        this.smoothGazeX = 0;
        this.smoothGazeY = 0;

        // Smoothing factor (0 = no smoothing, 1 = frozen)
        this.smoothingFactor = 0.60;

        // Dead zone - ignore tiny movements near centre
        this.deadZone = 0.04;

        // MediaPipe objects
        this.faceDetection = null;
        this.camera = null;

        // Tracking state
        this.faceDetected = false;
        this.usingMouseFallback = false;

        // ---- Debug UI elements ----
        this.debugPanel = document.getElementById('debugPanel');
        this.debugDot = document.getElementById('debugDot');
        this.debugText = document.getElementById('debugText');
        this.debugVideo = document.getElementById('debugVideo');   // mini preview video
        this.debugCanvas = document.getElementById('debugCanvas');  // bbox overlay
        this.debugCtx = this.debugCanvas ? this.debugCanvas.getContext('2d') : null;

        // Last detection result (bbox) for drawing
        this._lastBbox = null;

        console.log('FaceTracker created');
    }

    // ----------------------------------------------------------
    // Init
    // ----------------------------------------------------------
    async init() {
        this._setStatus('init', 'Inisialisasi kamera...');

        try {
            // ---- 1. Request camera stream ----
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
                audio: false
            });

            // Feed stream into hidden main video (used by MediaPipe Camera util)
            this.video.srcObject = stream;
            this.video.setAttribute('playsinline', '');
            await new Promise(resolve => {
                this.video.onloadedmetadata = () => { this.video.play(); resolve(); };
            });

            // Also feed the same stream into the debug mini-preview
            if (this.debugVideo) {
                this.debugVideo.srcObject = stream;
                this.debugVideo.play().catch(() => { });
            }

            console.log(`Camera ready: ${this.video.videoWidth}x${this.video.videoHeight}`);
            this._setStatus('searching', 'Kamera aktif – mencari wajah...');

            // ---- 2. Build MediaPipe Face Detection ----
            if (typeof FaceDetection === 'undefined') {
                console.error('MediaPipe FaceDetection not loaded!');
                this._setStatus('error', 'MediaPipe tidak ditemukan');
                return false;
            }

            this.faceDetection = new FaceDetection({
                locateFile: (file) =>
                    `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4/${file}`
            });

            this.faceDetection.setOptions({
                model: 'short',
                minDetectionConfidence: 0.5
            });

            this.faceDetection.onResults((results) => this._onResults(results));

            // ---- 3. Start MediaPipe Camera utility ----
            this.camera = new Camera(this.video, {
                onFrame: async () => {
                    if (this.isRunning && this.faceDetection) {
                        await this.faceDetection.send({ image: this.video });
                    }
                },
                width: 640,
                height: 480
            });

            await this.camera.start();

            this.isInitialized = true;
            this.isRunning = true;

            // Draw bounding-box loop (independent of detection rate)
            this._startDebugDrawLoop();

            console.log('FaceTracker (MediaPipe) initialized and running');
            return true;

        } catch (err) {
            console.warn('Camera/MediaPipe init failed, switching to mouse fallback:', err);
            this._activateMouseFallback();
            return false;   // tracker still "works" via mouse
        }
    }

    // ----------------------------------------------------------
    // MediaPipe results handler
    // ----------------------------------------------------------
    _onResults(results) {
        if (!this.isRunning) return;

        if (results.detections && results.detections.length > 0) {
            this.faceDetected = true;
            this._setStatus('detected', 'Wajah Terdeteksi');

            const det = results.detections[0];
            const bbox = det.boundingBox; // { xCenter, yCenter, width, height } all normalized

            // Store bbox for debug drawing
            this._lastBbox = bbox;

            // Gaze: invert X for mirror effect
            let rawX = (bbox.xCenter - 0.5) * -2.0;
            let rawY = (bbox.yCenter - 0.5) * 2.0;

            // Dead zone
            if (Math.abs(rawX) < this.deadZone) rawX = 0;
            if (Math.abs(rawY) < this.deadZone) rawY = 0;

            // Clamp
            this.gazeX = Math.max(-1, Math.min(1, rawX));
            this.gazeY = Math.max(-1, Math.min(1, rawY));

        } else {
            this.faceDetected = false;
            this._lastBbox = null;
            this._setStatus('searching', 'Mencari Wajah...');

            // Return to centre
            this.gazeX *= 0.92;
            this.gazeY *= 0.92;
            if (Math.abs(this.gazeX) < 0.01) this.gazeX = 0;
            if (Math.abs(this.gazeY) < 0.01) this.gazeY = 0;
        }

        // Exponential smoothing
        const f = this.smoothingFactor;
        this.smoothGazeX = this.smoothGazeX * f + this.gazeX * (1 - f);
        this.smoothGazeY = this.smoothGazeY * f + this.gazeY * (1 - f);
    }

    // ----------------------------------------------------------
    // Debug drawing loop (bbox overlay on mini preview)
    // ----------------------------------------------------------
    _startDebugDrawLoop() {
        const draw = () => {
            if (!this.debugCtx || !this.debugCanvas) return;

            const w = this.debugCanvas.offsetWidth;
            const h = this.debugCanvas.offsetHeight;

            // Keep canvas pixel size in sync with displayed size
            if (this.debugCanvas.width !== w || this.debugCanvas.height !== h) {
                this.debugCanvas.width = w;
                this.debugCanvas.height = h;
            }

            this.debugCtx.clearRect(0, 0, w, h);

            if (this._lastBbox) {
                const bbox = this._lastBbox;

                // MediaPipe bbox uses xCenter/yCenter + width/height (all 0-1)
                // The preview video is mirrored via CSS (scaleX(-1)),
                // so we invert x in canvas coords to match.
                const bx = (1 - bbox.xCenter - bbox.width / 2) * w;
                const by = (bbox.yCenter - bbox.height / 2) * h;
                const bw = bbox.width * w;
                const bh = bbox.height * h;

                // Bounding box
                this.debugCtx.strokeStyle = '#22c55e';
                this.debugCtx.lineWidth = 2;
                this.debugCtx.strokeRect(bx, by, bw, bh);

                // Dot at face centre
                const cx = (1 - bbox.xCenter) * w;
                const cy = bbox.yCenter * h;
                this.debugCtx.fillStyle = '#22c55e';
                this.debugCtx.beginPath();
                this.debugCtx.arc(cx, cy, 4, 0, Math.PI * 2);
                this.debugCtx.fill();

                // Gaze readout text
                this.debugCtx.fillStyle = 'rgba(0,0,0,0.6)';
                this.debugCtx.fillRect(2, h - 20, 130, 18);
                this.debugCtx.fillStyle = '#fff';
                this.debugCtx.font = '10px monospace';
                this.debugCtx.fillText(
                    `gaze x:${this.smoothGazeX.toFixed(2)} y:${this.smoothGazeY.toFixed(2)}`,
                    5, h - 7
                );
            }

            requestAnimationFrame(draw);
        };
        requestAnimationFrame(draw);
    }

    // ----------------------------------------------------------
    // Mouse / touch fallback
    // ----------------------------------------------------------
    _activateMouseFallback() {
        this.usingMouseFallback = true;
        this.isInitialized = true;
        this.isRunning = true;

        // Hide preview (no camera)
        if (document.getElementById('debugPreviewWrap')) {
            document.getElementById('debugPreviewWrap').style.display = 'none';
        }

        this._setStatus('mouse', 'Kamera Ditolak – Mode Mouse');

        const updateFromPointer = (x, y) => {
            if (!this.isRunning) return;
            let rawX = (x / window.innerWidth - 0.5) * 2.0;
            let rawY = (y / window.innerHeight - 0.5) * 2.0;
            rawX = Math.max(-1, Math.min(1, rawX));
            rawY = Math.max(-1, Math.min(1, rawY));
            this.gazeX = rawX;
            this.gazeY = rawY;
            // No smoothing needed for mouse – update smooth directly
            const f = 0.5; // lighter smoothing for mouse
            this.smoothGazeX = this.smoothGazeX * f + this.gazeX * (1 - f);
            this.smoothGazeY = this.smoothGazeY * f + this.gazeY * (1 - f);
        };

        window.addEventListener('mousemove', (e) => updateFromPointer(e.clientX, e.clientY));
        window.addEventListener('touchmove', (e) => {
            if (e.touches.length > 0) {
                updateFromPointer(e.touches[0].clientX, e.touches[0].clientY);
            }
        }, { passive: true });

        console.log('Mouse fallback active');
    }

    // ----------------------------------------------------------
    // Debug status UI helper
    // ----------------------------------------------------------
    _setStatus(state, text) {
        if (this.debugText) this.debugText.innerText = text;
        if (!this.debugDot) return;

        this.debugDot.className = ''; // clear all state classes
        switch (state) {
            case 'detected': this.debugDot.className = 'detected'; break;
            case 'searching': this.debugDot.className = 'searching'; break;
            case 'mouse': this.debugDot.className = 'mouse'; break;
            case 'error': this.debugDot.className = 'error'; break;
            default: break; // grey (init)
        }
    }

    // ----------------------------------------------------------
    // Public API (compatible with app.js)
    // ----------------------------------------------------------

    /** Get current smoothed gaze position. Returns { x, y } in -1..1 */
    getGaze() {
        return { x: this.smoothGazeX, y: this.smoothGazeY };
    }

    start() {
        if (!this.isInitialized) { this.init(); return; }
        this.isRunning = true;
        console.log('FaceTracker started');
    }

    stop() {
        this.isRunning = false;
        this.gazeX = 0; this.gazeY = 0;
        this.smoothGazeX = 0; this.smoothGazeY = 0;
        this._setStatus('init', 'Tracking dimatikan');
        console.log('FaceTracker stopped');
    }

    toggle() {
        if (this.isRunning) { this.stop(); } else { this.start(); }
        return this.isRunning;
    }

    /**
     * Pause tracking and RELEASE camera so another process (Python FER) can use it.
     * Call this when switching to Mirror or Conversation mode.
     */
    pause() {
        this.isRunning = false;
        this.paused = true;

        // Stop MediaPipe Camera utility
        if (this.camera) {
            this.camera.stop();
        }

        // Release getUserMedia tracks (frees /dev/video0)
        if (this.video && this.video.srcObject) {
            this.video.srcObject.getTracks().forEach(t => t.stop());
            this.video.srcObject = null;
        }

        // Clear debug preview
        if (this.debugVideo && this.debugVideo.srcObject) {
            this.debugVideo.srcObject.getTracks().forEach(t => t.stop());
            this.debugVideo.srcObject = null;
        }

        this.gazeX = 0; this.gazeY = 0;
        this.smoothGazeX = 0; this.smoothGazeY = 0;
        this._setStatus('init', 'Kamera di-release (mode FER)');
        console.log('[FaceTracker] Paused — camera released for Python FER');
    }

    /**
     * Resume tracking and RE-ACQUIRE camera from system.
     * Call this when switching back to Default mode.
     */
    async resume() {
        if (!this.paused) return;
        this.paused = false;
        console.log('[FaceTracker] Resuming — re-acquiring camera...');
        this._setStatus('init', 'Mengambil kamera kembali...');

        // Re-initialize the full pipeline
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
                audio: false
            });

            this.video.srcObject = stream;
            await new Promise(resolve => {
                this.video.onloadedmetadata = () => { this.video.play(); resolve(); };
            });

            if (this.debugVideo) {
                this.debugVideo.srcObject = stream;
                this.debugVideo.play().catch(() => { });
            }

            // Restart MediaPipe Camera utility
            if (this.faceDetection) {
                this.camera = new Camera(this.video, {
                    onFrame: async () => {
                        if (this.isRunning && this.faceDetection) {
                            await this.faceDetection.send({ image: this.video });
                        }
                    },
                    width: 640,
                    height: 480
                });
                await this.camera.start();
            }

            this.isRunning = true;
            this._setStatus('searching', 'Kamera aktif – mencari wajah...');
            console.log('[FaceTracker] Resumed — camera acquired');
        } catch (err) {
            console.warn('[FaceTracker] Resume failed, activating mouse fallback:', err);
            this._activateMouseFallback();
        }
    }

    destroy() {
        this.stop();
        if (this.camera) { this.camera.stop(); this.camera = null; }
        if (this.video && this.video.srcObject) {
            this.video.srcObject.getTracks().forEach(t => t.stop());
            this.video.srcObject = null;
        }
        this.faceDetection = null;
        console.log('FaceTracker destroyed');
    }
}

window.FaceTracker = FaceTracker;
