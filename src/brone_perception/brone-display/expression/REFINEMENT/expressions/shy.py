"""
expressions/shy.py
==================
Ekspresi SHY / KAWAII 'w' — mata bintang + pipi memerah + mulut 'w'.

Fitur unik:
  - Mata menggunakan draw_eye_sparkles (bintang 8-titik, bukan glint biasa)
  - Pipi memerah (blush) dari pre-rendered surface
  - Mulut berbentuk dua setengah lingkaran 'w'
"""

import pygame
import math

from core.constants import (
    WIDTH, center_x, BLACK,
    make_eye_rects, eye_width, eye_height,
)
from core.renderer import (
    create_eye_gradient, create_blush_surface,
    draw_eye_sparkles, draw_eyelid, draw_cables,
)
from core.loop import run_expression


# ── Konfigurasi Mulut ─────────────────────────────────────────────────────────
_MOUTH_Y       = 440
_ARC_RADIUS    = 40
_LINE_THICKNESS = 8

# ── Konfigurasi Blush ─────────────────────────────────────────────────────────
_BLUSH_W = 100
_BLUSH_H = 60


# ── Fungsi Gambar Mulut ───────────────────────────────────────────────────────

def draw_shy_mouth(surface: pygame.Surface) -> None:
    """Gambar mulut 'w' dua busur setengah lingkaran (tidak ada lidah)."""
    rect_left  = pygame.Rect(center_x - (_ARC_RADIUS * 2), _MOUTH_Y, _ARC_RADIUS * 2, _ARC_RADIUS * 2)
    rect_right = pygame.Rect(center_x,                      _MOUTH_Y, _ARC_RADIUS * 2, _ARC_RADIUS * 2)

    pygame.draw.arc(surface, BLACK, rect_left,  math.pi, 0, _LINE_THICKNESS)
    pygame.draw.arc(surface, BLACK, rect_right, math.pi, 0, _LINE_THICKNESS)

    # Titik sambungan agar arsitektur 'w' terlihat bersih
    r = _LINE_THICKNESS // 2
    pygame.draw.circle(surface, BLACK, (center_x - (_ARC_RADIUS * 2) + 2, _MOUTH_Y + _ARC_RADIUS), r)
    pygame.draw.circle(surface, BLACK, (center_x,                          _MOUTH_Y + _ARC_RADIUS), r)
    pygame.draw.circle(surface, BLACK, (center_x + (_ARC_RADIUS * 2) - 2,  _MOUTH_Y + _ARC_RADIUS), r)


# ── Entry Point ───────────────────────────────────────────────────────────────

def run():
    """Jalankan ekspresi shy sebagai window mandiri."""
    pygame.init()
    left_eye_rect, right_eye_rect = make_eye_rects()
    gradient = create_eye_gradient(eye_width, eye_height)
    blush    = create_blush_surface(_BLUSH_W, _BLUSH_H, alpha=150)

    def draw_frame(screen, blink_progress, current_time, pup_ox=0, pup_oy=0):
        draw_cables(screen, left_eye_rect, right_eye_rect, center_x, WIDTH)

        # Blush di bawah masing-masing mata
        screen.blit(blush, (left_eye_rect.centerx  - _BLUSH_W // 2, left_eye_rect.bottom  + 20))
        screen.blit(blush, (right_eye_rect.centerx - _BLUSH_W // 2, right_eye_rect.bottom + 20))

        draw_eye_sparkles(screen, left_eye_rect,  gradient, pup_ox, pup_oy)
        draw_eye_sparkles(screen, right_eye_rect, gradient, pup_ox, pup_oy)
        draw_eyelid(screen, left_eye_rect,  blink_progress)
        draw_eyelid(screen, right_eye_rect, blink_progress)
        draw_shy_mouth(screen)

    run_expression(draw_frame, caption="Robot Face - SHY")
