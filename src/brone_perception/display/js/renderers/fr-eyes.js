/**
 * fr-eyes.js
 * ==========
 * Semua fungsi gambar MATA untuk FaceRenderer:
 *   - drawEyeGradient          : Mata standar (gradasi ungu + glint putih)
 *   - drawEyelid               : Kelopak mata untuk animasi kedip
 *   - drawEyeGradientSparkles  : Mata dengan ornamen bintang (shy / happier)
 *   - drawPurpleEyeWithWave    : Mata ungu bergelombang (cry)
 *   - drawCartoonStream        : Aliran air mata kartun (cry)
 *
 * Dependencies: FRTransform, FRCables (untuk drawStar)
 */

const FREyes = (() => {

    // ── Warna (mirror dari colors object FaceRenderer) ──────────────────────
    const C = {
        black:        'rgb(0, 0, 0)',
        highlight:    'rgb(240, 245, 255)',
        highlightW:   'rgb(255, 255, 255)',
        eyeTop:       'rgb(80, 70, 150)',
        eyeBottom:    'rgb(0, 0, 0)',
        background:   'rgb(205, 215, 225)',
        eyeWater:     'rgb(130, 200, 255)',
        eyeBaseColor: 'rgb(40, 30, 70)',
        tearStream:   'rgb(170, 230, 255)',
        blueDot:      'rgb(150, 150, 255)',
    };

    // ──────────────────────────────────────────────────────────────────────────
    // MATA STANDAR
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Gambar mata standar dengan gradasi ungu dan highlight putih (glint).
     * Highlight bergerak mengikuti pupilOffsetX/Y untuk efek gaze tracking.
     *
     * @param {CanvasRenderingContext2D} ctx
     * @param {{ tx, ty, ts }} t       - Transform helpers
     * @param {{ x,y,width,height,centerX,centerY }} eye
     * @param {number} pupilOffsetX    - -1..1 (kiri → kanan)
     * @param {number} pupilOffsetY    - -1..1 (atas → bawah)
     * @param {number} maxShiftX       - Maks pixel shift horizontal (ref coords)
     * @param {number} maxShiftY       - Maks pixel shift vertikal  (ref coords)
     */
    function drawEyeGradient(ctx, t, eye, pupilOffsetX, pupilOffsetY, maxShiftX = 20, maxShiftY = 22) {
        const shiftX = pupilOffsetX * maxShiftX;
        const shiftY = pupilOffsetY * maxShiftY;

        // 1. Outline hitam
        ctx.fillStyle = C.black;
        ctx.beginPath();
        ctx.ellipse(t.tx(eye.centerX), t.ty(eye.centerY),
            t.ts(eye.width / 2 + 4), t.ts(eye.height / 2 + 4), 0, 0, Math.PI * 2);
        ctx.fill();

        // 2. Gradient fill + clip region
        const grad = ctx.createLinearGradient(
            t.tx(eye.x), t.ty(eye.y),
            t.tx(eye.x), t.ty(eye.y + eye.height)
        );
        grad.addColorStop(0, C.eyeTop);
        grad.addColorStop(1, C.eyeBottom);

        ctx.save();
        ctx.beginPath();
        ctx.ellipse(t.tx(eye.centerX), t.ty(eye.centerY),
            t.ts(eye.width / 2), t.ts(eye.height / 2), 0, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.clip();   // gambar highlight di dalam ellips

        // 3. Highlight (bergerak mengikuti gaze)
        const glintX = eye.centerX + shiftX;
        const glintY = eye.centerY + shiftY;

        ctx.fillStyle = C.highlight;
        ctx.beginPath();
        ctx.arc(t.tx(glintX), t.ty(glintY), t.ts(22), 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = C.eyeTop;
        ctx.beginPath();
        ctx.arc(t.tx(glintX + 10), t.ty(glintY + 10), t.ts(10), 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = C.highlight;
        ctx.beginPath();
        ctx.arc(t.tx(glintX - 5), t.ty(glintY + 35), t.ts(6), 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // KELOPAK MATA (BLINK)
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Gambar kelopak mata yang menutup dari atas ke bawah.
     * @param {number} blinkProgress - 0.0 = terbuka, 1.0 = tertutup
     */
    function drawEyelid(ctx, t, eye, blinkProgress) {
        if (blinkProgress <= 0) return;

        const lidHeight = eye.height * blinkProgress;

        ctx.fillStyle = C.background;
        ctx.fillRect(
            t.tx(eye.x - 5),
            t.ty(eye.y - 5),
            t.ts(eye.width + 10),
            t.ts(lidHeight + 5)
        );

        const lineY = Math.min(eye.y + lidHeight, eye.y + eye.height);
        ctx.strokeStyle = C.black;
        ctx.lineWidth   = t.ts(6);
        ctx.beginPath();
        ctx.moveTo(t.tx(eye.x - 5),              t.ty(lineY));
        ctx.lineTo(t.tx(eye.x + eye.width + 5),  t.ty(lineY));
        ctx.stroke();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // MATA DENGAN BINTANG (SHY / HAPPIER)
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Mata standar dengan ornamen bintang 8-titik menggantikan glint biasa.
     * Membutuhkan FRCables.drawStar.
     */
    function drawEyeGradientSparkles(ctx, t, eye, pupilOffsetX, pupilOffsetY, maxShiftX = 20, maxShiftY = 22) {
        const shiftX = pupilOffsetX * maxShiftX;
        const shiftY = pupilOffsetY * maxShiftY;

        // Outline
        ctx.fillStyle = C.black;
        ctx.beginPath();
        ctx.ellipse(t.tx(eye.centerX), t.ty(eye.centerY),
            t.ts(eye.width / 2 + 4), t.ts(eye.height / 2 + 4), 0, 0, Math.PI * 2);
        ctx.fill();

        // Gradient fill + clip
        const grad = ctx.createLinearGradient(
            t.tx(eye.x), t.ty(eye.y),
            t.tx(eye.x), t.ty(eye.y + eye.height)
        );
        grad.addColorStop(0, C.eyeTop);
        grad.addColorStop(1, C.eyeBottom);

        ctx.save();
        ctx.beginPath();
        ctx.ellipse(t.tx(eye.centerX), t.ty(eye.centerY),
            t.ts(eye.width / 2), t.ts(eye.height / 2), 0, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.clip();

        // Bintang (bergerak dengan gaze)
        const glintX = eye.x + eye.width * 0.35 + shiftX;
        const glintY = eye.y + eye.height * 0.3  + shiftY;

        FRCables.drawStar(ctx, t, glintX, glintY, 35, C.highlightW);

        ctx.fillStyle = C.highlightW;
        ctx.beginPath();
        ctx.arc(t.tx(glintX + 20), t.ty(glintY + 20), t.ts(5), 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = C.blueDot;
        ctx.beginPath();
        ctx.arc(t.tx(glintX - 12), t.ty(glintY + 12), t.ts(3), 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // MATA UNGU BERGELOMBANG (CRY)
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Mata ungu gelap dengan efek air bergelombang.
     * @param {number} animTime - Waktu animasi kontinu (detik)
     */
    function drawPurpleEyeWithWave(ctx, t, eye, animTime, pupilOffsetX, pupilOffsetY, maxShiftX = 20, maxShiftY = 22) {
        const shiftX = pupilOffsetX * maxShiftX;
        const shiftY = pupilOffsetY * maxShiftY;

        // Outline
        ctx.fillStyle = C.eyeBaseColor;
        ctx.beginPath();
        ctx.ellipse(t.tx(eye.centerX), t.ty(eye.centerY),
            t.ts(eye.width / 2 + 4), t.ts(eye.height / 2 + 4), 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.save();
        ctx.beginPath();
        ctx.ellipse(t.tx(eye.centerX), t.ty(eye.centerY),
            t.ts(eye.width / 2), t.ts(eye.height / 2), 0, 0, Math.PI * 2);
        ctx.clip();

        // Base ungu gelap
        ctx.fill();

        // Gelombang air
        ctx.fillStyle = C.eyeWater;
        ctx.beginPath();
        const waterLevelY = eye.y + eye.height * 0.55;

        ctx.moveTo(t.tx(eye.x), t.ty(eye.y + eye.height));
        ctx.lineTo(t.tx(eye.x), t.ty(waterLevelY));

        for (let x = 0; x <= eye.width; x += 5) {
            const waveH = 5 * Math.sin(0.15 * x + animTime * 3) + shiftY;
            ctx.lineTo(t.tx(eye.x + x), t.ty(waterLevelY + waveH));
        }

        ctx.lineTo(t.tx(eye.x + eye.width), t.ty(eye.y + eye.height));
        ctx.closePath();
        ctx.fill();

        // Glint (bergerak dengan gaze)
        const g1X = eye.x + 35 + shiftX;
        const g1Y = eye.y + 45 + shiftY;
        ctx.fillStyle = C.highlightW;
        ctx.beginPath();
        ctx.arc(t.tx(g1X), t.ty(g1Y), t.ts(22), 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.arc(t.tx(eye.x + 55 + shiftX), t.ty(eye.y + 80 + shiftY), t.ts(6), 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();

        // Outline mata
        ctx.strokeStyle = C.black;
        ctx.lineWidth   = t.ts(6);
        ctx.beginPath();
        ctx.ellipse(t.tx(eye.centerX), t.ty(eye.centerY),
            t.ts(eye.width / 2), t.ts(eye.height / 2), 0, 0, Math.PI * 2);
        ctx.stroke();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // ALIRAN AIR MATA (CRY)
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Gambar aliran air mata kartun dengan tetes bergerak ke bawah.
     * @param {number} startX    - Titik X awal (tengah bawah mata)
     * @param {number} startY    - Titik Y awal
     * @param {number} animTime  - Waktu animasi kontinu (detik)
     */
    function drawCartoonStream(ctx, t, startX, startY, animTime) {
        const widthTop    = 20;
        const widthBottom = 30;
        const refHeight   = 600;

        ctx.fillStyle = C.tearStream;
        ctx.beginPath();

        let first = true;
        for (let y = startY; y < refHeight; y += 10) {
            const prog     = (y - startY) / (refHeight - startY);
            const currentW = widthTop + (widthBottom - widthTop) * prog;
            const wiggle   = Math.sin(y * 0.05 + animTime * 3) * 4;
            const px       = startX - currentW / 2 + wiggle;
            if (first) { ctx.moveTo(t.tx(px), t.ty(y)); first = false; }
            else        { ctx.lineTo(t.tx(px), t.ty(y)); }
        }

        for (let y = refHeight; y >= startY; y -= 10) {
            const prog     = (y - startY) / (refHeight - startY);
            const currentW = widthTop + (widthBottom - widthTop) * prog;
            const wiggle   = Math.sin(y * 0.05 + animTime * 3) * 4;
            ctx.lineTo(t.tx(startX + currentW / 2 + wiggle), t.ty(y));
        }

        ctx.closePath();
        ctx.fill();

        // Tetes berjalan
        for (let i = 0; i < 3; i++) {
            const offset = i * 250;
            const dropY  = startY + ((animTime * 80 + offset) % (refHeight - startY + 100));
            if (dropY < refHeight) {
                ctx.fillStyle = C.highlightW;
                ctx.beginPath();
                ctx.ellipse(t.tx(startX), t.ty(dropY), t.ts(8), t.ts(15), 0, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    return {
        drawEyeGradient,
        drawEyelid,
        drawEyeGradientSparkles,
        drawPurpleEyeWithWave,
        drawCartoonStream,
    };
})();

window.FREyes = FREyes;
