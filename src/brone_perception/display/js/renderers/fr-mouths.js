/**
 * fr-mouths.js
 * ============
 * Semua fungsi gambar MULUT untuk FaceRenderer:
 *   - drawHappyMouth    : Mulut senyum lebar (idle / happy / happier)
 *   - drawSpeakingMouth : Mulut oval dinamis (speaking)
 *   - drawSadMouth      : Mulut frown/cemberut (sad)
 *   - drawShockMouth    : Mulut oval squash & stretch (shock / load)
 *   - drawCryMouth      : Mulut wailing parabola (cry)
 *   - drawShyMouth      : Mulut 'w' dua busur (shy)
 *
 * Dependencies: FRTransform (semua fungsi menerima objek transform `t`)
 */

const FRMouths = (() => {

    const C = {
        black:     'rgb(0, 0, 0)',
        mouthDark: 'rgb(40, 40, 40)',
        tongue:    'rgb(230, 130, 100)',
    };

    // ──────────────────────────────────────────────────────────────────────────
    // Helper: bangun polygon mouth points
    // ──────────────────────────────────────────────────────────────────────────

    function _buildHappyPoints(centerX) {
        const mouthW           = 220;
        const mouthTopY        = 420;
        const curveTopSag      = 20;
        const curveBottomDepth = 100;
        const steps            = 60;

        const pts = [];
        for (let i = 0; i <= steps; i++) {
            const t  = i / steps;
            const px = (centerX - mouthW / 2) + t * mouthW;
            const py = mouthTopY + curveTopSag * 4 * t * (1 - t);
            pts.push({ x: px, y: py });
        }

        const a      = mouthW / 2;
        const b      = curveBottomDepth;
        const bottom = [];
        for (let i = 0; i <= steps; i++) {
            const t  = i / steps;
            const px = (centerX - mouthW / 2) + t * mouthW;
            const dx = px - centerX;
            const py = mouthTopY + b * Math.sqrt(Math.max(0, 1 - (dx / a) ** 2));
            bottom.push({ x: px, y: py });
        }
        bottom.reverse();
        return { pts: [...pts, ...bottom], mouthW, mouthTopY, curveBottomDepth };
    }

    // ──────────────────────────────────────────────────────────────────────────
    // HAPPY MOUTH
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Mulut senyum lebar dengan lidah di dalam.
     * Digunakan untuk state 'idle', 'happy', dan 'happier'.
     */
    function drawHappyMouth(ctx, t, centerX) {
        const { pts, mouthW, mouthTopY, curveBottomDepth } = _buildHappyPoints(centerX);

        _fillPolygon(ctx, t, pts, C.mouthDark);

        // Lidah: ellips kecil di dalam mulut
        const tongueX = centerX;
        const tongueY = mouthTopY + 60;
        const tongueW = (mouthW - 80) / 2;
        const tongueH = 40;

        ctx.fillStyle = C.tongue;
        ctx.beginPath();
        ctx.ellipse(t.tx(tongueX), t.ty(tongueY), t.ts(tongueW), t.ts(tongueH), 0, 0, Math.PI * 2);
        ctx.fill();

        _strokePolygon(ctx, t, pts, 8);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // SPEAKING MOUTH
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Mulut oval yang membuka-tutup saat bicara.
     * @param {number} speakingPhase - Nilai fase sinusoidal (bertambah setiap frame)
     */
    function drawSpeakingMouth(ctx, t, centerX, speakingPhase) {
        const openness = 0.5 + 0.5 * Math.sin(speakingPhase);
        const mouthTopY = 460;
        const mouthW    = 120 + openness * 30;
        const mouthH    = 50  + openness * 60;

        // Outline hitam
        ctx.fillStyle = C.black;
        ctx.beginPath();
        ctx.ellipse(t.tx(centerX), t.ty(mouthTopY), t.ts(mouthW / 2 + 4), t.ts(mouthH / 2 + 4), 0, 0, Math.PI * 2);
        ctx.fill();

        // Rongga gelap
        ctx.fillStyle = C.mouthDark;
        ctx.beginPath();
        ctx.ellipse(t.tx(centerX), t.ty(mouthTopY), t.ts(mouthW / 2), t.ts(mouthH / 2), 0, 0, Math.PI * 2);
        ctx.fill();

        // Lidah (setengah bawah)
        ctx.fillStyle = C.tongue;
        ctx.beginPath();
        ctx.ellipse(
            t.tx(centerX),
            t.ty(mouthTopY + mouthH * 0.15),
            t.ts(mouthW * 0.4), t.ts(mouthH * 0.35),
            0, 0, Math.PI
        );
        ctx.fill();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // SAD MOUTH
    // ──────────────────────────────────────────────────────────────────────────

    function drawSadMouth(ctx, t, centerX) {
        const mouthW  = 150;
        const mouthH  = 60;
        const baseY   = 460;
        const steps   = 60;

        const pts      = [];
        const radiusX  = mouthW / 2;
        const radiusY  = mouthH;

        for (let i = 0; i <= steps; i++) {
            const u  = i / steps;
            const px = (centerX - mouthW / 2) + u * mouthW;
            const dx = px - centerX;
            const py = baseY - radiusY * Math.sqrt(Math.max(0, 1 - (dx / radiusX) ** 2));
            pts.push({ x: px, y: py });
        }

        const bottomSag = 15;
        for (let i = steps; i >= 0; i--) {
            const u  = i / steps;
            const px = (centerX - mouthW / 2) + u * mouthW;
            const py = baseY - bottomSag * Math.sin(u * Math.PI);
            pts.push({ x: px, y: py });
        }

        _fillPolygon(ctx, t, pts, C.mouthDark);
        _strokePolygon(ctx, t, pts, 8);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // SHOCK MOUTH (juga dipakai oleh load)
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Mulut oval squash & stretch mengikuti blink progress.
     * @param {number} blinkProgress  - 0.0–1.0
     * @param {number} centerY        - Posisi Y center mulut (default 440)
     * @param {number} baseMouthW     - Lebar dasar (default 120)
     * @param {number} baseMouthH     - Tinggi dasar (default 140)
     */
    function drawShockMouth(ctx, t, centerX, blinkProgress,
                            centerY = 440, baseMouthW = 120, baseMouthH = 140) {
        const currentH = Math.max(6, baseMouthH * (1.0 - blinkProgress));
        const currentW = baseMouthW + blinkProgress * 40;

        ctx.fillStyle = C.mouthDark;
        ctx.beginPath();
        ctx.ellipse(t.tx(centerX), t.ty(centerY), t.ts(currentW / 2), t.ts(currentH / 2), 0, 0, Math.PI * 2);
        ctx.fill();

        if (currentH > 10) {
            ctx.fillStyle = C.tongue;
            ctx.beginPath();
            ctx.ellipse(
                t.tx(centerX), t.ty(centerY + currentH * 0.15),
                t.ts(currentW * 0.4), t.ts(currentH * 0.35),
                0, 0, Math.PI
            );
            ctx.fill();
        }

        ctx.strokeStyle = C.black;
        ctx.lineWidth   = t.ts(6);
        ctx.beginPath();
        if (currentH > 10) {
            ctx.ellipse(t.tx(centerX), t.ty(centerY), t.ts(currentW / 2), t.ts(currentH / 2), 0, 0, Math.PI * 2);
        } else {
            ctx.moveTo(t.tx(centerX - currentW / 2), t.ty(centerY));
            ctx.lineTo(t.tx(centerX + currentW / 2), t.ty(centerY));
        }
        ctx.stroke();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // CRY MOUTH
    // ──────────────────────────────────────────────────────────────────────────

    function drawCryMouth(ctx, t, centerX) {
        const mouthW  = 160;
        const mouthH  = 90;
        const baseY   = 480;
        const steps   = 60;

        const pts = [];

        for (let i = 0; i <= steps; i++) {
            const u  = i / steps;
            const px = (centerX - mouthW / 2) + u * mouthW;
            const py = baseY - mouthH * 4 * u * (1 - u);
            pts.push({ x: px, y: py });
        }

        for (let i = steps; i >= 0; i--) {
            const u  = i / steps;
            const px = (centerX - mouthW / 2) + u * mouthW;
            const py = baseY - 20 * 4 * u * (1 - u);
            pts.push({ x: px, y: py });
        }

        _fillPolygon(ctx, t, pts, C.mouthDark);
        _strokePolygon(ctx, t, pts, 8);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // SHY MOUTH ('w')
    // ──────────────────────────────────────────────────────────────────────────

    function drawShyMouth(ctx, t, centerX) {
        const mouthY      = 440;
        const arcRadius   = 35;
        const thickness   = 8;

        ctx.strokeStyle = C.black;
        ctx.lineWidth   = t.ts(thickness);
        ctx.lineCap     = 'round';

        ctx.beginPath();
        ctx.arc(t.tx(centerX - arcRadius), t.ty(mouthY), t.ts(arcRadius), 0, Math.PI, false);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(t.tx(centerX + arcRadius), t.ty(mouthY), t.ts(arcRadius), 0, Math.PI, false);
        ctx.stroke();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Private helpers
    // ──────────────────────────────────────────────────────────────────────────

    function _fillPolygon(ctx, t, pts, color) {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(t.tx(pts[0].x), t.ty(pts[0].y));
        for (let i = 1; i < pts.length; i++) {
            ctx.lineTo(t.tx(pts[i].x), t.ty(pts[i].y));
        }
        ctx.closePath();
        ctx.fill();
    }

    function _strokePolygon(ctx, t, pts, width = 8) {
        ctx.strokeStyle = C.black;
        ctx.lineWidth   = t.ts(width);
        ctx.beginPath();
        ctx.moveTo(t.tx(pts[0].x), t.ty(pts[0].y));
        for (let i = 1; i < pts.length; i++) {
            ctx.lineTo(t.tx(pts[i].x), t.ty(pts[i].y));
        }
        ctx.closePath();
        ctx.stroke();
    }

    return {
        drawHappyMouth,
        drawSpeakingMouth,
        drawSadMouth,
        drawShockMouth,
        drawCryMouth,
        drawShyMouth,
    };
})();

window.FRMouths = FRMouths;
