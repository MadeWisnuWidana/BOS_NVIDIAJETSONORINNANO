"""
expressions/sad.py
==================
Ekspresi SAD — mulut melengkung ke atas (frown / cemberut).
Mata tetap menggunakan standar draw_eye_gradient.
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

_mouth_w   = 180
_mouth_h   = 75    # Kedalaman lengkungan
_base_y    = 480
_steps     = 80

def _build_mouth_points():
    pts      = []
    radius_x = _mouth_w / 2
    radius_y = _mouth_h

    # Kurva atas (melengkung ke atas)
    for i in range(_steps + 1):
        t  = i / _steps
        px = (center_x - _mouth_w // 2) + (t * _mouth_w)
        dx = px - center_x
        offset_y = radius_y * math.sqrt(max(0, 1 - (dx / radius_x) ** 2))
        py = _base_y - offset_y
        pts.append((px, py))

    # Kurva bawah (sedikit melengkung ke atas membentuk rongga tipis)
    bottom_sag = 10
    for i in range(_steps, -1, -1):
        t  = i / _steps
        px = (center_x - _mouth_w // 2) + (t * _mouth_w)
        py = _base_y - (bottom_sag * math.sin(t * math.pi))
        pts.append((px, py))

    return pts

_STATIC_MOUTH_POINTS = _build_mouth_points()

_box_w = _mouth_w + 10
_box_h = _mouth_h + 10 + 10   # bottom_sag + margin
_box_x = center_x - _mouth_w // 2
_box_y = _base_y - _mouth_h
_LOCAL_MOUTH_POINTS = [(px - _box_x, py - _box_y) for px, py in _STATIC_MOUTH_POINTS]


# ── Fungsi Gambar Mulut ───────────────────────────────────────────────────────

def draw_sad_mouth(surface: pygame.Surface) -> None:
    """Gambar mulut sedih (melengkung ke atas / frown) dengan lidah."""
    pygame.draw.polygon(surface, MOUTH_DARK, _STATIC_MOUTH_POINTS)

    # Kanvas memori mini (local masking lidah)
    mouth_surf = pygame.Surface((_box_w, _box_h), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_surf, (255, 255, 255, 255), _LOCAL_MOUTH_POINTS)

    tongue_surf      = pygame.Surface((_box_w, _box_h), pygame.SRCALPHA)
    tongue_w         = _mouth_w * 0.6
    tongue_fill_h    = 35
    tongue_rect      = pygame.Rect(
        _box_w // 2 - tongue_w // 2,
        _box_h - tongue_fill_h - 5,
        tongue_w,
        tongue_fill_h * 2,
    )
    pygame.draw.ellipse(tongue_surf, TONGUE, tongue_rect)

    mouth_surf.blit(tongue_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(mouth_surf, (_box_x, _box_y))

    pygame.draw.polygon(surface, BLACK, _STATIC_MOUTH_POINTS, 8)
    pygame.draw.aalines(surface, BLACK, True, _STATIC_MOUTH_POINTS)


# ── Entry Point ───────────────────────────────────────────────────────────────

def run():
    """Jalankan ekspresi sad sebagai window mandiri."""
    pygame.init()
    left_eye_rect, right_eye_rect = make_eye_rects()
    gradient = create_eye_gradient(eye_width, eye_height)

    def draw_frame(screen, blink_progress, current_time, pup_ox=0, pup_oy=0):
        draw_cables(screen, left_eye_rect, right_eye_rect, center_x, WIDTH)
        draw_eye_gradient(screen, left_eye_rect,  gradient, pup_ox, pup_oy)
        draw_eye_gradient(screen, right_eye_rect, gradient, pup_ox, pup_oy)
        draw_eyelid(screen, left_eye_rect,  blink_progress)
        draw_eyelid(screen, right_eye_rect, blink_progress)
        draw_sad_mouth(screen)

    run_expression(draw_frame, caption="Robot Face - SAD")
