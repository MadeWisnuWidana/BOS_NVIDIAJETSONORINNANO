"""
expressions/happy.py
====================
Ekspresi HAPPY — mulut senyum lebar dengan lidah.

Digunakan langsung oleh ekspresi 'happy' (idle default).
Ekspresi 'happier' also menggunakan fungsi yang sama + blush + sparkle eye
(lihat happier.py).
"""

import pygame
import math

from core.constants import (
    WIDTH, center_x, MOUTH_DARK, TONGUE, BLACK,
    make_eye_rects, eye_width, eye_height,
)
from core.renderer import (
    create_eye_gradient, draw_eye_gradient, draw_eyelid, draw_cables,
)
from core.loop import run_expression


# ── Pre-calculate Titik Mulut (dihitung 1× saat import) ──────────────────────

_mouth_w           = 320
_mouth_top_y       = 420
_curve_top_sag     = 30
_curve_bottom_depth = 140
_steps             = 60

def _build_mouth_points():
    pts = []
    for i in range(_steps + 1):
        t  = i / _steps
        px = (center_x - _mouth_w // 2) + (t * _mouth_w)
        py = _mouth_top_y + (_curve_top_sag * 4 * t * (1 - t))
        pts.append((px, py))

    a = _mouth_w / 2
    b = _curve_bottom_depth
    bottom = []
    for i in range(_steps + 1):
        t  = i / _steps
        px = (center_x - _mouth_w // 2) + (t * _mouth_w)
        dx = px - center_x
        offset_y = b * math.sqrt(max(0, 1 - (dx / a) ** 2))
        py = _mouth_top_y + offset_y
        bottom.append((px, py))

    pts.extend(reversed(bottom))
    return pts

_STATIC_MOUTH_POINTS = _build_mouth_points()
_LOCAL_MOUTH_POINTS  = [
    (px - (center_x - _mouth_w // 2), py - _mouth_top_y)
    for px, py in _STATIC_MOUTH_POINTS
]


# ── Fungsi Gambar Mulut ───────────────────────────────────────────────────────

def draw_happy_mouth(surface: pygame.Surface) -> None:
    """Gambar mulut senyum lebar dengan lidah. Tidak ada animasi dinamis."""
    pygame.draw.polygon(surface, MOUTH_DARK, _STATIC_MOUTH_POINTS)

    mouth_box_h = _curve_bottom_depth + 10
    mouth_surf  = pygame.Surface((_mouth_w, mouth_box_h), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_surf, (255, 255, 255, 255), _LOCAL_MOUTH_POINTS)

    tongue_surf      = pygame.Surface((_mouth_w, mouth_box_h), pygame.SRCALPHA)
    local_tongue_rect = pygame.Rect(20, 60, _mouth_w - 40, 110)
    pygame.draw.ellipse(tongue_surf, TONGUE, local_tongue_rect)

    mouth_surf.blit(tongue_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(mouth_surf, (center_x - _mouth_w // 2, _mouth_top_y))

    pygame.draw.polygon(surface, BLACK, _STATIC_MOUTH_POINTS, 8)
    pygame.draw.aalines(surface, BLACK, True, _STATIC_MOUTH_POINTS)


# ── Entry Point ───────────────────────────────────────────────────────────────

def run():
    """Jalankan ekspresi happy sebagai window mandiri."""
    pygame.init()  # diperlukan sebelum make_eye_rects & create_eye_gradient
    left_eye_rect, right_eye_rect = make_eye_rects()
    gradient = create_eye_gradient(eye_width, eye_height)

    def draw_frame(screen, blink_progress, current_time, pup_ox=0, pup_oy=0):
        draw_cables(screen, left_eye_rect, right_eye_rect, center_x, WIDTH)
        draw_eye_gradient(screen, left_eye_rect,  gradient, pup_ox, pup_oy)
        draw_eye_gradient(screen, right_eye_rect, gradient, pup_ox, pup_oy)
        draw_eyelid(screen, left_eye_rect,  blink_progress)
        draw_eyelid(screen, right_eye_rect, blink_progress)
        draw_happy_mouth(screen)

    run_expression(draw_frame, caption="Robot Face - HAPPY")
