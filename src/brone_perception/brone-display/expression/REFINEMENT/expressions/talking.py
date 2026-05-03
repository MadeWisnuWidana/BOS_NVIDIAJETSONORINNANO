"""
expressions/talking.py
======================
Ekspresi TALKING STATE — mulut dinamis yang membuka-tutup saat bicara.
Tekan SPASI untuk toggle bicara / diam.

Fitur unik:
  - Bibir atas STATIS (pre-calculated).
  - Bibir bawah DINAMIS (dihitung ulang per frame berdasarkan time_counter).
  - Lidah naik-turun mengikuti seberapa lebar mulut terbuka.
  - Toggle bicara/diam via SPACE key (atau bisa dikontrol dari luar via MQTT).
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


# ── Konfigurasi Mulut ─────────────────────────────────────────────────────────
_mouth_w       = 320
_mouth_top_y   = 420
_curve_top_sag = 30
_steps         = 60
_DEFAULT_DEPTH = 140


# ── Pre-calculate Bibir Atas (statis, tidak bergerak saat bicara) ─────────────
def _build_top_points():
    pts = []
    for i in range(_steps + 1):
        t  = i / _steps
        px = (center_x - _mouth_w // 2) + (t * _mouth_w)
        py = _mouth_top_y + (_curve_top_sag * 4 * t * (1 - t))
        pts.append((px, py))
    return pts

_STATIC_TOP_POINTS = _build_top_points()


# ── Fungsi Gambar Mulut Dinamis ───────────────────────────────────────────────

def draw_talking_mouth(
    surface: pygame.Surface,
    talk_time: float,
    is_talking: bool,
) -> None:
    """
    Gambar mulut bicara dengan buka-tutup sinusoidal.

    Args:
        talk_time  : Nilai counter waktu yang bertambah setiap frame (bicara aktif).
        is_talking : True = mulut animasi buka-tutup, False = mulut diam terbuka.
    """
    if is_talking:
        wave          = math.sin(talk_time * 0.15)
        depth         = max(30, 100 + wave * 60)   # 30–160 px
    else:
        depth         = _DEFAULT_DEPTH

    # Hitung bibir bawah (dinamis)
    a            = _mouth_w / 2
    bottom_pts   = []
    for i in range(_steps + 1):
        t  = i / _steps
        px = (center_x - _mouth_w // 2) + (t * _mouth_w)
        dx = px - center_x
        offset_y = depth * math.sqrt(max(0, 1 - (dx / a) ** 2))
        py = _mouth_top_y + offset_y
        bottom_pts.append((px, py))

    mouth_pts = _STATIC_TOP_POINTS + list(reversed(bottom_pts))

    # Bounding box kanvas lokal (ukurannya dinamis)
    box_w = _mouth_w + 10
    box_h = int(depth + 40)
    box_x = center_x - _mouth_w // 2
    box_y = _mouth_top_y
    local_pts = [(px - box_x, py - box_y) for px, py in mouth_pts]

    # Gambar rongga gelap
    pygame.draw.polygon(surface, MOUTH_DARK, mouth_pts)

    # Kanvas lokal masking lidah
    mouth_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_surf, (255, 255, 255, 255), local_pts)

    tongue_surf   = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    tongue_base_y = 60
    if depth < 70:
        tongue_base_y += 30   # lidah turun kalau mulut mengecil
    local_tongue_rect = pygame.Rect(20, tongue_base_y, _mouth_w - 40, 110)
    pygame.draw.ellipse(tongue_surf, TONGUE, local_tongue_rect)

    mouth_surf.blit(tongue_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(mouth_surf, (box_x, box_y))

    # Outline
    pygame.draw.polygon(surface, BLACK, mouth_pts, 8)
    pygame.draw.aalines(surface, BLACK, True, mouth_pts)


# ── Entry Point ───────────────────────────────────────────────────────────────

def run():
    """
    Jalankan ekspresi talking sebagai window mandiri.
    Tekan SPASI untuk toggle bicara / diam.
    """
    pygame.init()
    left_eye_rect, right_eye_rect = make_eye_rects()
    gradient = create_eye_gradient(eye_width, eye_height)

    is_talking   = False
    talk_time    = 0.0

    def handle_keydown(event):
        nonlocal is_talking
        if event.key == pygame.K_SPACE:
            is_talking = not is_talking
            print(f"Bicara: {is_talking}")

    def draw_frame(screen, blink_progress, current_time, pup_ox=0, pup_oy=0):
        nonlocal talk_time
        if is_talking:
            talk_time += 1

        draw_cables(screen, left_eye_rect, right_eye_rect, center_x, WIDTH)
        draw_eye_gradient(screen, left_eye_rect,  gradient, pup_ox, pup_oy)
        draw_eye_gradient(screen, right_eye_rect, gradient, pup_ox, pup_oy)
        draw_eyelid(screen, left_eye_rect,  blink_progress)
        draw_eyelid(screen, right_eye_rect, blink_progress)
        draw_talking_mouth(screen, talk_time, is_talking)

    # Loop khusus: tambahkan key handler
    from core.constants import BG_COLOR
    clock = pygame.time.Clock()
    from core.blink import BlinkController
    blinker = pygame.display.set_mode((WIDTH, pygame.display.Info().current_h))
    # Gunakan run_expression standar dgn gaze tetap + inject key handler
    screen = pygame.display.set_mode((WIDTH, 600))
    pygame.display.set_caption("Robot Face - TALKING (SPASI = toggle)")
    blinker = BlinkController()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                handle_keydown(event)

        current_time   = pygame.time.get_ticks()
        blink_progress = blinker.update(current_time)

        screen.fill(BG_COLOR)
        draw_frame(screen, blink_progress, current_time)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    import sys; sys.exit()
