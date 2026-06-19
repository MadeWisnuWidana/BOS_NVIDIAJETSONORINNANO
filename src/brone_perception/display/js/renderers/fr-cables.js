/**
 * fr-cables.js
 * ============
 * Fungsi-fungsi gambar elemen wajah yang BERSIFAT STATIS / DEKORASI:
 *   - drawCables   : kabel robot antara dua mata + kabel sudut atas
 *   - drawBlush    : pipi memerah (ellips semi-transparan)
 *   - drawStar     : ornamen bintang 8-titik (untuk shy / happier)
 *
 * Dependency: FRTransform (harus dimuat sebelumnya)
 * Semua fungsi menerima objek `t` (transform) sebagai parameter pertama.
 */

const FRCables = (() => {

    /**
     * Gambar tiga kabel robot: kiri, kanan, dan V-shape tengah.
     * @param {CanvasRenderingContext2D} ctx
     * @param {{ tx, ty, ts }} t    - Transform object dari FRTransform
     * @param {{ x,y,width,height,centerX,centerY }} leftEye
     * @param {{ x,y,width,height,centerX,centerY }} rightEye
     * @param {number} centerX      - Titik tengah referensi (biasanya 400)
     */
    function drawCables(ctx, t, leftEye, rightEye, centerX) {
        const elbowY = leftEye.y - 50;

        ctx.strokeStyle = 'rgb(0,0,0)';
        ctx.lineWidth   = t.ts(4);
        ctx.lineCap     = 'round';
        ctx.lineJoin    = 'round';

        // Kabel kiri
        ctx.beginPath();
        ctx.moveTo(t.tx(-20),              t.ty(60));
        ctx.lineTo(t.tx(leftEye.centerX),  t.ty(elbowY));
        ctx.lineTo(t.tx(leftEye.centerX),  t.ty(leftEye.y));
        ctx.stroke();

        // Kabel kanan
        ctx.beginPath();
        ctx.moveTo(t.tx(820),              t.ty(60));
        ctx.lineTo(t.tx(rightEye.centerX), t.ty(elbowY));
        ctx.lineTo(t.tx(rightEye.centerX), t.ty(rightEye.y));
        ctx.stroke();

        // V-shape tengah
        ctx.beginPath();
        ctx.moveTo(t.tx(leftEye.x + leftEye.width - 10), t.ty(leftEye.centerY));
        ctx.lineTo(t.tx(centerX),                         t.ty(leftEye.centerY + 40));
        ctx.lineTo(t.tx(rightEye.x + 10),                 t.ty(rightEye.centerY));
        ctx.stroke();
    }

    /**
     * Gambar pipi memerah (ellips semi-transparan) di bawah salah satu mata.
     * @param {CanvasRenderingContext2D} ctx
     * @param {{ tx, ty, ts }} t
     * @param {{ centerX, y, height }} eye
     * @param {string} color - CSS color string (rgba)
     */
    function drawBlush(ctx, t, eye, color = 'rgba(255, 180, 200, 0.6)') {
        const blushW  = 80;
        const blushH  = 45;
        const offset  = eye.centerX > 400 ? 15 : -15;

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.ellipse(
            t.tx(eye.centerX + offset),
            t.ty(eye.y + eye.height + 15),
            t.ts(blushW / 2), t.ts(blushH / 2),
            0, 0, Math.PI * 2
        );
        ctx.fill();
    }

    /**
     * Gambar bintang 8-titik di posisi (x, y) dengan ukuran `size`.
     * @param {CanvasRenderingContext2D} ctx
     * @param {{ tx, ty }} t
     * @param {number} x
     * @param {number} y
     * @param {number} size
     * @param {string} color
     */
    function drawStar(ctx, t, x, y, size, color = 'rgb(240, 245, 255)') {
        const half  = size / 2;
        const inner = size / 5;

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(t.tx(x),          t.ty(y - half));
        ctx.lineTo(t.tx(x + inner),  t.ty(y - inner));
        ctx.lineTo(t.tx(x + half),   t.ty(y));
        ctx.lineTo(t.tx(x + inner),  t.ty(y + inner));
        ctx.lineTo(t.tx(x),          t.ty(y + half));
        ctx.lineTo(t.tx(x - inner),  t.ty(y + inner));
        ctx.lineTo(t.tx(x - half),   t.ty(y));
        ctx.lineTo(t.tx(x - inner),  t.ty(y - inner));
        ctx.closePath();
        ctx.fill();
    }

    return { drawCables, drawBlush, drawStar };
})();

window.FRCables = FRCables;
