/**
 * fr-blink.js
 * ===========
 * BlinkController — logika animasi kedip mata untuk FaceRenderer.
 *
 * Dependency: NONE (standalone, tidak bergantung module lain)
 *
 * Usage:
 *   const blinker = new FRBlink.BlinkController();
 *   // di setiap frame:
 *   blinker.update(currentTime);
 *   // blinker.progress : 0.0 (terbuka) – 1.0 (tertutup)
 */

const FRBlink = (() => {
    class BlinkController {
        constructor() {
            this.progress      = 0;
            this.state         = 'idle';    // 'idle' | 'closing' | 'opening'
            this.lastBlinkTime = 0;
            this.nextDelay     = _randomDelay();
            this._nextState    = null;      // pending expression swap
        }

        /**
         * Perbarui animasi blink.
         * @param {number} currentTime - performance.now() atau timestamp rAF
         * @param {string|null} pendingNextState - Ekspresi yang menunggu giliran swap
         */
        update(currentTime, pendingNextState = null) {
            // Percepat blink saat ada transisi ekspresi
            const speed = (pendingNextState) ? 0.20 : 0.08;

            if (this.state === 'idle') {
                if (currentTime - this.lastBlinkTime > this.nextDelay) {
                    this.state    = 'closing';
                    this.progress = 0;
                }
            } else if (this.state === 'closing') {
                this.progress += speed;
                if (this.progress >= 1.0) {
                    this.progress = 1.0;
                    this.state    = 'opening';
                    // Titik swap: mata tertutup penuh → boleh ganti ekspresi
                    if (pendingNextState) {
                        this._nextState = pendingNextState;
                    }
                }
            } else if (this.state === 'opening') {
                this.progress -= speed;
                if (this.progress <= 0) {
                    this.progress      = 0;
                    this.state         = 'idle';
                    this.lastBlinkTime = currentTime;
                    this.nextDelay     = _randomDelay();
                }
            }
        }

        /** Paksa kedip sekarang (misal saat transisi ekspresi). */
        forceBlink() {
            if (this.state === 'idle' || this.state === 'opening') {
                this.state    = 'closing';
                this.progress = Math.max(this.progress, 0);
            }
        }

        /** Ambil ekspresi yang sudah siap di-swap (setelah mata tertutup penuh). */
        consumeNextState() {
            const s = this._nextState;
            this._nextState = null;
            return s;
        }
    }

    function _randomDelay() {
        return 2000 + Math.random() * 4000;
    }

    return { BlinkController };
})();

window.FRBlink = FRBlink;
