/**
 * fr-transform.js
 * ===============
 * Coordinate transform helpers untuk FaceRenderer.
 * Mengkonversi koordinat dari reference space (800×600) ke canvas aktual.
 *
 * Dimuat sebelum fr-blink.js dan file renderer lainnya.
 * Memiliki dependency: NONE (harus dimuat pertama)
 */

const FRTransform = (() => {
    /**
     * Buat set fungsi transform berdasarkan canvas dan reference size.
     * @param {number} canvasW  - Lebar canvas aktual (pixel)
     * @param {number} canvasH  - Tinggi canvas aktual (pixel)
     * @param {number} refW     - Lebar reference (default 800)
     * @param {number} refH     - Tinggi reference (default 600)
     * @returns {{ tx, ty, ts, scale, offsetX, offsetY }}
     */
    function create(canvasW, canvasH, refW = 800, refH = 600) {
        const scale   = Math.min(canvasW / refW, canvasH / refH);
        const offsetX = (canvasW - refW * scale) / 2;
        const offsetY = (canvasH - refH * scale) / 2;

        return {
            scale,
            offsetX,
            offsetY,
            /** Konversi X koordinat reference → canvas */
            tx: (x) => offsetX + x * scale,
            /** Konversi Y koordinat reference → canvas */
            ty: (y) => offsetY + y * scale,
            /** Konversi size → canvas (uniform scaling) */
            ts: (s) => s * scale,
        };
    }

    return { create };
})();

window.FRTransform = FRTransform;
