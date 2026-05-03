"""
expressions/happier.py
======================
Ekspresi HAPPIER / SHY+SPARKLE — mulut happy lebar + pipi blush + mata bintang.

Perbedaan dari 'happy':
  - Mata menggunakan draw_eye_sparkles (bukan draw_eye_gradient standar)
  - Pipi memerah (blush) aktif
"""

import pygame

from core.constants import (
    WIDTH, center_x,
    make_eye_rects, eye_width, eye_height,
)
from core.renderer import (
    create_eye_gradient, create_blush_surface,
    draw_eye_sparkles, draw_eyelid, draw_cables,
)
from core.loop import run_expression
from expressions.happy import draw_happy_mouth     # re-use mulut yang sama


# ── Konfigurasi Blush ─────────────────────────────────────────────────────────
_BLUSH_W = 90
_BLUSH_H = 55


# ── Entry Point ───────────────────────────────────────────────────────────────

def run():
    """Jalankan ekspresi happier sebagai window mandiri."""
    pygame.init()
    left_eye_rect, right_eye_rect = make_eye_rects()
    gradient = create_eye_gradient(eye_width, eye_height)
    blush    = create_blush_surface(_BLUSH_W, _BLUSH_H, alpha=120)

    def draw_frame(screen, blink_progress, current_time, pup_ox=0, pup_oy=0):
        draw_cables(screen, left_eye_rect, right_eye_rect, center_x, WIDTH)

        # Blush (sedikit lebih ke luar dibanding shy)
        screen.blit(blush, (left_eye_rect.centerx  - _BLUSH_W // 2 - 25, left_eye_rect.bottom  + 15))
        screen.blit(blush, (right_eye_rect.centerx - _BLUSH_W // 2 + 25, right_eye_rect.bottom + 15))

        draw_eye_sparkles(screen, left_eye_rect,  gradient, pup_ox, pup_oy)
        draw_eye_sparkles(screen, right_eye_rect, gradient, pup_ox, pup_oy)
        draw_eyelid(screen, left_eye_rect,  blink_progress)
        draw_eyelid(screen, right_eye_rect, blink_progress)
        draw_happy_mouth(screen)

    run_expression(draw_frame, caption="Robot Face - HAPPIER")
