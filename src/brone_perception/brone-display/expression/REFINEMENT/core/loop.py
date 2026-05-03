"""
core/loop.py
============
run_expression() — Pygame game loop standar yang digunakan oleh semua ekspresi.

Developer cukup menyediakan satu fungsi callback:

    def draw_frame(screen, blink_progress, current_time):
        # gambar semua elemen ekspresi di sini

Kemudian panggil:

    from core.loop import run_expression
    run_expression(draw_frame, caption="Nama Ekspresi")

Keterangan tambahan:
  - Loop otomatis mengurus blink via BlinkController.
  - Target 60 FPS.
  - Mendukung parameter pup_ox / pup_oy (saccades) lewat `gaze_fn` opsional.
"""

import pygame
import sys
from .constants import WIDTH, HEIGHT, BG_COLOR
from .blink import BlinkController


def run_expression(
    draw_frame,
    caption: str = "Robot Face",
    gaze_fn=None,
) -> None:
    """
    Jalankan pygame loop untuk satu ekspresi robot face.

    Args:
        draw_frame : Callable(screen, blink_progress, current_time, **kwargs).
                     Dipanggil setiap frame setelah layar di-clear.
        caption    : Judul window pygame.
        gaze_fn    : Callable() → (pup_ox, pup_oy) opsional untuk saccades.
                     Jika None, offset pupil = (0, 0).
    """
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(caption)
    clock  = pygame.time.Clock()

    blinker = BlinkController()

    running = True
    while running:
        # ── Event handling ─────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # ── Update state ───────────────────────────────────────────────────────
        current_time   = pygame.time.get_ticks()
        blink_progress = blinker.update(current_time)
        pup_ox, pup_oy = gaze_fn() if gaze_fn else (0, 0)

        # ── Draw frame ─────────────────────────────────────────────────────────
        screen.fill(BG_COLOR)
        draw_frame(
            screen,
            blink_progress=blink_progress,
            current_time=current_time,
            pup_ox=pup_ox,
            pup_oy=pup_oy,
        )

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()
