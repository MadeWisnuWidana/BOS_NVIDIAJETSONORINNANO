"""
expressions/load.py
===================
Ekspresi LOAD — mata bergaya dengan iris/pupil yang dapat dirotasi
(digunakan saat robot sedang "berpikir" / loading).

Fitur unik:
  - Mata menggunakan draw_rotated_layered_eye (sclera + iris + pupil, bisa dirotasi)
  - Mulut menggunakan oval squash & stretch sama seperti shock.
"""

import pygame
import math

from core.constants import (
    WIDTH, center_x,
    MOUTH_DARK, TONGUE, BLACK,
    COLOR_BASE_TOP, COLOR_BASE_BOTTOM,
    COLOR_SCLERA, COLOR_IRIS, COLOR_PUPIL,
    eye_width, eye_height, dist_from_center,
    make_eye_rects,
)
from core.renderer import draw_eyelid, draw_cables
from core.loop import run_expression


# ── Konfigurasi Mulut (sama dengan shock) ─────────────────────────────────────
_BASE_MOUTH_W   = 220
_BASE_MOUTH_H   = 130
_MOUTH_CENTER_Y = 420 + _BASE_MOUTH_H // 2


# ── Pre-render Gradient Mata Load ─────────────────────────────────────────────

def _create_load_gradient(w: int, h: int) -> pygame.Surface:
    """Gradient vertikal custom untuk mata bergaya (warna berbeda dari standar)."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        ratio = max(0.0, min(1.0, y / h))
        r = int(COLOR_BASE_TOP[0] * (1 - ratio) + COLOR_BASE_BOTTOM[0] * ratio)
        g = int(COLOR_BASE_TOP[1] * (1 - ratio) + COLOR_BASE_BOTTOM[1] * ratio)
        b = int(COLOR_BASE_TOP[2] * (1 - ratio) + COLOR_BASE_BOTTOM[2] * ratio)
        pygame.draw.line(surf, (r, g, b), (0, y), (w, y))
    return surf


# ── Gambar Mata Berlapis + Rotasi ─────────────────────────────────────────────

def draw_rotated_layered_eye(
    target_surface: pygame.Surface,
    dest_rect: pygame.Rect,
    pre_rendered_base: pygame.Surface,
    gaze_dir: float,
    angle: float,
    pup_ox: int = 0,
    pup_oy: int = 0,
) -> None:
    """
    Gambar mata berlapis (gradient + sclera + iris + pupil) yang bisa dirotasi.

    Args:
        gaze_dir         : Arah tatapan (-1 = kiri, +1 = kanan).
        angle            : Sudut rotasi mata dalam derajat.
        pup_ox, pup_oy   : Offset pupil untuk saccades.
    """
    w, h       = dest_rect.width, dest_rect.height
    diagonal   = int(math.sqrt(w ** 2 + h ** 2)) + 10
    canvas_size = (diagonal, diagonal)
    canvas     = pygame.Surface(canvas_size, pygame.SRCALPHA)
    cx, cy     = diagonal // 2, diagonal // 2

    # Konten mata
    content    = pygame.Surface((w, h), pygame.SRCALPHA)
    content.blit(pre_rendered_base, (0, 0))

    base_shift = 25 * gaze_dir

    # Sclera (putih)
    sclera_w, sclera_h = w * 0.75, h * 0.85
    sclera_x = (w - sclera_w) / 2 + (base_shift * 0.8)
    pygame.draw.ellipse(content, COLOR_SCLERA,
                        (sclera_x, (h - sclera_h) / 2 + 5, sclera_w, sclera_h))

    # Iris (hijau gelap)
    iris_w, iris_h = w * 0.55, h * 0.65
    iris_x = (w - iris_w) / 2 + (base_shift * 1.0)
    pygame.draw.ellipse(content, COLOR_IRIS,
                        (iris_x, (h - iris_h) / 2 + 8, iris_w, iris_h))

    # Pupil (terang, bisa digeser via saccades)
    pupil_w, pupil_h = w * 0.30, h * 0.35
    pupil_x = (w - pupil_w) / 2 + (base_shift * 1.2) + pup_ox
    pupil_y = (h - pupil_h) / 2 + 10 + pup_oy
    pygame.draw.ellipse(content, COLOR_PUPIL,
                        (pupil_x, pupil_y, pupil_w, pupil_h))

    # Masking ellips agar konten tidak keluar dari bentuk mata
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(mask, (255, 255, 255), (0, 0, w, h))
    content.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    canvas.blit(content, (cx - w // 2, cy - h // 2))
    pygame.draw.ellipse(canvas, BLACK, (cx - w // 2, cy - h // 2, w, h), 6)

    # Rotasi
    if angle != 0:
        canvas = pygame.transform.rotate(canvas, angle)

    new_rect = canvas.get_rect(center=dest_rect.center)
    target_surface.blit(canvas, new_rect.topleft)


# ── Gambar Mulut Load (Squash & Stretch, sama dengan shock) ──────────────────

def draw_load_mouth(surface: pygame.Surface, blink_progress: float) -> None:
    """Mulut oval yang gepeng mengikuti blink progress."""
    current_h = max(6, _BASE_MOUTH_H * (1.0 - blink_progress))
    current_w = _BASE_MOUTH_W + (blink_progress * 40)

    mouth_rect = pygame.Rect(0, 0, current_w, current_h)
    mouth_rect.center = (center_x, _MOUTH_CENTER_Y)

    if current_h > 10:
        pygame.draw.ellipse(surface, MOUTH_DARK, mouth_rect)

        clip_rect = pygame.Rect(mouth_rect.left, mouth_rect.centery,
                                mouth_rect.width, mouth_rect.height // 2)
        surface.set_clip(clip_rect)
        pygame.draw.ellipse(surface, TONGUE, mouth_rect)
        surface.set_clip(None)

        pygame.draw.ellipse(surface, BLACK, mouth_rect, 6)
    else:
        pygame.draw.line(surface, BLACK,
                         (mouth_rect.left, mouth_rect.centery),
                         (mouth_rect.right, mouth_rect.centery), 6)


# ── Entry Point ───────────────────────────────────────────────────────────────

def run():
    """Jalankan ekspresi load sebagai window mandiri."""
    pygame.init()
    # Mata load menggunakan center yang berbeda
    from core.constants import center_x as cx, eye_y, eye_width as ew, eye_height as eh, dist_from_center as dfc
    left_eye_rect  = pygame.Rect(0, 0, ew, eh)
    right_eye_rect = pygame.Rect(0, 0, ew, eh)
    left_eye_rect.center  = (cx - dfc - ew // 2, eye_y + eh // 2)
    right_eye_rect.center = (cx + dfc + ew // 2, eye_y + eh // 2)

    pre_rendered_base = _create_load_gradient(ew, eh)

    def draw_frame(screen, blink_progress, current_time, pup_ox=0, pup_oy=0):
        draw_cables(screen, left_eye_rect, right_eye_rect, cx, WIDTH)

        draw_rotated_layered_eye(screen, left_eye_rect,  pre_rendered_base, gaze_dir=-1, angle=0,  pup_ox=pup_ox, pup_oy=pup_oy)
        draw_rotated_layered_eye(screen, right_eye_rect, pre_rendered_base, gaze_dir=-1, angle=10, pup_ox=pup_ox, pup_oy=pup_oy)

        draw_eyelid(screen, left_eye_rect,  blink_progress)
        draw_eyelid(screen, right_eye_rect, blink_progress)
        draw_load_mouth(screen, blink_progress)

    run_expression(draw_frame, caption="Robot Face - LOAD")
