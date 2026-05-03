"""
expressions/shock.py
====================
Ekspresi SHOCK / OVAL SURPRISED — mulut oval yang squash & stretch
mengikuti animasi blink (semakin merem → mulut semakin gepeng & lebar).
"""

import pygame

from core.constants import (
    WIDTH, center_x, MOUTH_DARK, TONGUE, BLACK,
    make_eye_rects, eye_width, eye_height,
)
from core.renderer import (
    create_eye_gradient, draw_eye_gradient, draw_eyelid, draw_cables,
)
from core.loop import run_expression


# ── Konfigurasi Mulut ─────────────────────────────────────────────────────────
_BASE_MOUTH_W = 220
_BASE_MOUTH_H = 160
_MOUTH_CENTER_Y = 440


# ── Fungsi Gambar Mulut ───────────────────────────────────────────────────────

def draw_shock_mouth(surface: pygame.Surface, blink_progress: float) -> None:
    """
    Gambar mulut oval mengejutkan dengan efek squash & stretch.

    Semakin besar blink_progress (semakin merem) → mulut semakin gepeng & lebar.
    """
    current_h = max(6, _BASE_MOUTH_H * (1.0 - blink_progress))
    current_w = _BASE_MOUTH_W + (blink_progress * 40)

    mouth_rect = pygame.Rect(0, 0, current_w, current_h)
    mouth_rect.center = (center_x, _MOUTH_CENTER_Y)

    if current_h > 10:
        # Rongga gelap
        pygame.draw.ellipse(surface, MOUTH_DARK, mouth_rect)

        # Lidah (hanya bagian bawah ellips)
        clip_rect = pygame.Rect(mouth_rect.left, mouth_rect.centery,
                                mouth_rect.width, mouth_rect.height // 2)
        surface.set_clip(clip_rect)
        pygame.draw.ellipse(surface, TONGUE, mouth_rect)
        surface.set_clip(None)

        # Outline
        pygame.draw.ellipse(surface, BLACK, mouth_rect, 6)
    else:
        # Mulut hampir tertutup → tampilkan sebagai garis tipis
        pygame.draw.line(
            surface, BLACK,
            (mouth_rect.left, mouth_rect.centery),
            (mouth_rect.right, mouth_rect.centery),
            6,
        )


# ── Entry Point ───────────────────────────────────────────────────────────────

def run():
    """Jalankan ekspresi shock sebagai window mandiri."""
    pygame.init()
    left_eye_rect, right_eye_rect = make_eye_rects()
    gradient = create_eye_gradient(eye_width, eye_height)

    def draw_frame(screen, blink_progress, current_time, pup_ox=0, pup_oy=0):
        draw_cables(screen, left_eye_rect, right_eye_rect, center_x, WIDTH)
        draw_eye_gradient(screen, left_eye_rect,  gradient, pup_ox, pup_oy)
        draw_eye_gradient(screen, right_eye_rect, gradient, pup_ox, pup_oy)
        draw_eyelid(screen, left_eye_rect,  blink_progress)
        draw_eyelid(screen, right_eye_rect, blink_progress)
        draw_shock_mouth(screen, blink_progress)

    run_expression(draw_frame, caption="Robot Face - SHOCK")
