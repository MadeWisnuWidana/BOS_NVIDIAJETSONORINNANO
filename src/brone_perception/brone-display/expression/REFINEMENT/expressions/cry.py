"""
expressions/cry.py
==================
Ekspresi CRY — mata ungu bergelombang + aliran air mata animasi + mulut sedih.

Fitur unik ekspresi ini:
  - Mata menggunakan draw_purple_eye_with_wave (bukan draw_eye_gradient standar)
  - Air mata mengalir dari bawah masing-masing mata (draw_tear_stream)
  - Mulut berbentuk "W" terbalik (melengkung ke atas tajam)
"""

import pygame
import math

from core.constants import (
    WIDTH, HEIGHT, center_x,
    MOUTH_DARK, BLACK, HIGHLIGHT_W,
    EYE_BASE_COLOR, EYE_WATER, TEAR_STREAM_COLOR,
    make_eye_rects, eye_width, eye_height,
)
from core.renderer import draw_eyelid, draw_cables
from core.loop import run_expression


# ── Pre-render Eye Mask (potong gelombang air agar tidak keluar ellips) ───────
def _build_eye_mask(w: int, h: int) -> pygame.Surface:
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (255, 255, 255, 255), (0, 0, w, h))
    return surf

# Pre-calculate titik mulut sedih "wailing" (parabola ke atas tajam)
_mouth_w  = 200
_mouth_h  = 100
_base_y   = 520
_steps    = 60

def _build_mouth_points():
    pts = []
    for i in range(_steps + 1):
        t  = i / _steps
        px = (center_x - _mouth_w // 2) + (t * _mouth_w)
        py = _base_y - (_mouth_h * 4 * t * (1 - t))    # parabola ke atas
        pts.append((px, py))

    for i in range(_steps, -1, -1):
        t  = i / _steps
        px = (center_x - _mouth_w // 2) + (t * _mouth_w)
        py = _base_y - (20 * 4 * t * (1 - t))           # parabola landai
        pts.append((px, py))

    return pts

_STATIC_MOUTH_POINTS = _build_mouth_points()
_box_x = center_x - _mouth_w // 2
_box_y = _base_y  - _mouth_h
_box_w = _mouth_w
_box_h = _mouth_h
_LOCAL_MOUTH_POINTS  = [(px - _box_x, py - _box_y) for px, py in _STATIC_MOUTH_POINTS]


# ── Gambar Mata Ungu Bergelombang ─────────────────────────────────────────────

def draw_purple_eye_with_wave(
    surface: pygame.Surface,
    rect: pygame.Rect,
    eye_mask: pygame.Surface,
    time_val: float,
    pup_ox: int = 0,
    pup_oy: int = 0,
) -> None:
    """
    Gambar mata ungu gelap dengan efek air bergelombang di bagian bawah.

    Args:
        eye_mask  : Pre-rendered SRCALPHA surface berbentuk ellips (porong gelombang).
        time_val  : Nilai waktu kontinu untuk animasi gelombang.
    """
    # Dasar mata (ungu gelap)
    pygame.draw.ellipse(surface, EYE_BASE_COLOR, rect)

    # Wave surface
    wave_surf    = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    water_level  = rect.height * 0.55

    water_pts = []
    for x in range(rect.width):
        wave_height = 5 * math.sin(0.15 * x + time_val)
        water_pts.append((x, water_level + wave_height + pup_oy))

    water_pts.append((rect.width, rect.height))
    water_pts.append((0, rect.height))
    pygame.draw.polygon(wave_surf, EYE_WATER, water_pts)

    # Potong agar tidak keluar dari ellips mata
    wave_surf.blit(eye_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(wave_surf, rect.topleft)

    # Outline + glint
    pygame.draw.ellipse(surface, BLACK, rect, 6)
    pygame.draw.circle(surface, HIGHLIGHT_W, (rect.left + 35 + pup_ox, rect.top + 45 + pup_oy), 22)
    pygame.draw.circle(surface, HIGHLIGHT_W, (rect.left + 55 + pup_ox, rect.top + 80 + pup_oy),  6)


# ── Gambar Aliran Air Mata ────────────────────────────────────────────────────

def draw_tear_stream(
    surface: pygame.Surface,
    start_x: int,
    start_y: int,
    time_val: float,
) -> None:
    """
    Gambar aliran air mata kartun yang mengalir ke bawah dengan wiggle.
    Tiga tetes transparan (highlight) bergerak ke bawah secara loop.
    """
    stream_pts   = []
    width_top    = 40
    width_bottom = 50

    for y in range(start_y, HEIGHT, 10):
        prog      = (y - start_y) / (HEIGHT - start_y)
        current_w = width_top + (width_bottom - width_top) * prog
        wiggle    = math.sin(y * 0.05 + time_val) * 4
        stream_pts.append((start_x - current_w / 2 + wiggle, y))

    for y in range(HEIGHT, start_y, -10):
        prog      = (y - start_y) / (HEIGHT - start_y)
        current_w = width_top + (width_bottom - width_top) * prog
        wiggle    = math.sin(y * 0.05 + time_val) * 4
        stream_pts.append((start_x + current_w / 2 + wiggle, y))

    pygame.draw.polygon(surface, TEAR_STREAM_COLOR, stream_pts)

    # Tiga bulatan sumber air mata di ujung atas
    pygame.draw.circle(surface, TEAR_STREAM_COLOR, (start_x - 15, start_y + 5), 10)
    pygame.draw.circle(surface, TEAR_STREAM_COLOR, (start_x,      start_y + 8), 12)
    pygame.draw.circle(surface, TEAR_STREAM_COLOR, (start_x + 15, start_y + 5), 10)

    # Tiga tetes berjalan ke bawah dengan offset
    for i in range(3):
        offset  = i * 250
        drop_speed = 25
        drop_y  = start_y + ((time_val * drop_speed + offset) % (HEIGHT - start_y + 100))
        if drop_y < HEIGHT:
            h_rect = pygame.Rect(start_x - 8, drop_y, 16, 35)
            pygame.draw.ellipse(surface, HIGHLIGHT_W, h_rect)


# ── Gambar Mulut Tangis ───────────────────────────────────────────────────────

def draw_cry_mouth(surface: pygame.Surface) -> None:
    """Gambar mulut menangis (parabola ke atas tajam, tanpa lidah)."""
    pygame.draw.polygon(surface, MOUTH_DARK, _STATIC_MOUTH_POINTS)

    mouth_surf = pygame.Surface((_box_w, _box_h), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_surf, (255, 255, 255, 255), _LOCAL_MOUTH_POINTS)
    surface.blit(mouth_surf, (_box_x, _box_y))

    pygame.draw.polygon(surface, BLACK, _STATIC_MOUTH_POINTS, 8)
    pygame.draw.aalines(surface, BLACK, True, _STATIC_MOUTH_POINTS)


# ── Entry Point ───────────────────────────────────────────────────────────────

def run():
    """Jalankan ekspresi cry sebagai window mandiri."""
    pygame.init()
    left_eye_rect, right_eye_rect = make_eye_rects()
    eye_mask = _build_eye_mask(eye_width, eye_height)

    time_counter = 0.0

    def draw_frame(screen, blink_progress, current_time, pup_ox=0, pup_oy=0):
        nonlocal time_counter
        time_counter += 0.1

        draw_cables(screen, left_eye_rect, right_eye_rect, center_x, WIDTH)

        # Air mata di belakang mata agar tidak tertutup outline
        draw_tear_stream(screen, left_eye_rect.centerx,  left_eye_rect.bottom  - 20, time_counter)
        draw_tear_stream(screen, right_eye_rect.centerx, right_eye_rect.bottom - 20, time_counter)

        draw_purple_eye_with_wave(screen, left_eye_rect,  eye_mask, time_counter,     pup_ox, pup_oy)
        draw_purple_eye_with_wave(screen, right_eye_rect, eye_mask, time_counter + 2, pup_ox, pup_oy)

        draw_eyelid(screen, left_eye_rect,  blink_progress)
        draw_eyelid(screen, right_eye_rect, blink_progress)
        draw_cry_mouth(screen)

    run_expression(draw_frame, caption="Robot Face - CRY")
