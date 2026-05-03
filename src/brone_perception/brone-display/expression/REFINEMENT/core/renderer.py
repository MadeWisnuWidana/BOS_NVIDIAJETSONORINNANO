"""
core/renderer.py
================
Fungsi-fungsi gambar yang DIGUNAKAN BERSAMA oleh semua ekspresi:
  - draw_eye_gradient          : mata standar dengan gradasi ungu
  - draw_eye_sparkles          : mata با ornamen bintang (shy / happier)
  - draw_eyelid                : kelopak mata untuk animasi kedip
  - draw_cables                : kabel robot antara dua mata
  - draw_star                  : ornamen bintang 8-titik
  - create_eye_gradient        : pre-render surface gradasi (panggil 1× saat init)
  - create_blush_surface       : pre-render pipi memerah (panggil 1× saat init)
"""

import pygame
import math
from .constants import (
    BLACK, HIGHLIGHT, HIGHLIGHT_W, EYE_TOP, BG_COLOR
)


# ══════════════════════════════════════════════════════════════════════════════
# PRE-RENDER HELPERS (dipanggil SEKALI saat init, bukan setiap frame)
# ══════════════════════════════════════════════════════════════════════════════

def create_eye_gradient(w: int, h: int) -> pygame.Surface:
    """
    Buat surface gradasi vertikal EYE_TOP → EYE_BOTTOM berukuran (w × h).
    Gunakan hasil ini bersama BLEND_RGBA_MULT untuk mengisi ellips mata.
    """
    gradient_tiny = pygame.Surface((1, 2))
    gradient_tiny.fill(EYE_TOP,    (0, 0, 1, 1))
    gradient_tiny.fill((0, 0, 0),  (0, 1, 1, 1))
    return pygame.transform.smoothscale(gradient_tiny, (w, h))


def create_blush_surface(w: int, h: int, alpha: int = 130) -> pygame.Surface:
    """
    Buat surface ellips pipi memerah dengan transparansi.

    Args:
        w, h   : Ukuran surface.
        alpha  : Opacity 0–255.
    """
    from .constants import BLUSH_COLOR
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (*BLUSH_COLOR, alpha), (0, 0, w, h))
    return surf


# ══════════════════════════════════════════════════════════════════════════════
# GAMBAR MATA
# ══════════════════════════════════════════════════════════════════════════════

def draw_eye_gradient(
    surface: pygame.Surface,
    rect: pygame.Rect,
    pre_rendered_gradient: pygame.Surface,
    pup_ox: int = 0,
    pup_oy: int = 0,
) -> None:
    """
    Gambar satu mata dengan gradasi ungu dan highlight putih (glint).

    Args:
        surface             : Surface tujuan (biasanya layar utama).
        rect                : pygame.Rect posisi dan ukuran mata.
        pre_rendered_gradient: Surface gradasi yang sudah di-pre-render.
        pup_ox, pup_oy      : Offset pupil/glint untuk efek melirik (Saccades).
    """
    # 1. Outline hitam tebal
    pygame.draw.ellipse(surface, BLACK, rect.inflate(12, 12))

    # 2. Tempel gradasi (sangat hemat RAM vs. menggambar ulang setiap frame)
    eye_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(eye_surf, (255, 255, 255), (0, 0, rect.width, rect.height))
    eye_surf.blit(pre_rendered_gradient, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(eye_surf, rect.topleft)

    # 3. Highlights (bergerak mengikuti pup_ox / pup_oy)
    glint_x = rect.left + int(rect.width * 0.3) + pup_ox
    glint_y = rect.top  + int(rect.height * 0.25) + pup_oy

    pygame.draw.circle(surface, HIGHLIGHT,  (glint_x,     glint_y),     int(rect.width * 0.18))
    pygame.draw.circle(surface, EYE_TOP,    (glint_x + 8, glint_y + 8), int(rect.width * 0.08))

    small_x = glint_x - 5
    small_y = glint_y + int(rect.height * 0.3)
    pygame.draw.circle(surface, HIGHLIGHT, (small_x, small_y), int(rect.width * 0.05))


def draw_eye_sparkles(
    surface: pygame.Surface,
    rect: pygame.Rect,
    pre_rendered_gradient: pygame.Surface,
    pup_ox: int = 0,
    pup_oy: int = 0,
) -> None:
    """
    Gambar mata dengan ornamen bintang 8-titik (untuk ekspresi shy / happier).
    """
    # Outline hitam
    pygame.draw.ellipse(surface, BLACK, rect.inflate(12, 12))

    # Gradasi
    eye_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(eye_surf, (255, 255, 255), (0, 0, rect.width, rect.height))
    eye_surf.blit(pre_rendered_gradient, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(eye_surf, rect.topleft)

    # Posisi glint (bisa digeser untuk saccades)
    glint_x = rect.left + int(rect.width * 0.35) + pup_ox
    glint_y = rect.top  + int(rect.height * 0.3)  + pup_oy

    draw_star(surface, HIGHLIGHT_W, glint_x, glint_y, 45)
    pygame.draw.circle(surface, HIGHLIGHT_W, (glint_x + 25, glint_y + 25), 6)
    pygame.draw.circle(surface, (150, 150, 255), (glint_x - 15, glint_y + 15), 4)


# ══════════════════════════════════════════════════════════════════════════════
# KELOPAK MATA (BLINK)
# ══════════════════════════════════════════════════════════════════════════════

def draw_eyelid(
    surface: pygame.Surface,
    rect: pygame.Rect,
    progress: float,
) -> None:
    """
    Gambar kelopak mata yang menutup dari atas ke bawah.

    Args:
        progress: 0.0 = terbuka penuh, 1.0 = tertutup penuh.
    """
    if progress <= 0:
        return

    lid_height = rect.height * progress
    cover_rect = pygame.Rect(rect.left - 6, rect.top - 6, rect.width + 12, lid_height + 6)
    pygame.draw.rect(surface, BG_COLOR, cover_rect)

    line_y = rect.top + lid_height
    if line_y > rect.bottom:
        line_y = rect.bottom

    pygame.draw.line(surface, BLACK, (rect.left - 6, line_y), (rect.right + 6, line_y), 6)


# ══════════════════════════════════════════════════════════════════════════════
# KABEL ROBOT
# ══════════════════════════════════════════════════════════════════════════════

def draw_cables(
    surface: pygame.Surface,
    left_eye_rect: pygame.Rect,
    right_eye_rect: pygame.Rect,
    center_x: int,
    width: int,
) -> None:
    """
    Gambar kabel-kabel robot: dua kabel dari sudut atas dan satu kabel
    penghubung V-shape antar dua mata.
    """
    elbow_y = left_eye_rect.top - 50

    # Kabel kiri (dari pojok kiri atas layar)
    pygame.draw.lines(surface, BLACK, False, [
        (-20, 60),
        (left_eye_rect.centerx, elbow_y),
        (left_eye_rect.centerx, left_eye_rect.top),
    ], 5)

    # Kabel kanan (dari pojok kanan atas layar)
    pygame.draw.lines(surface, BLACK, False, [
        (width + 20, 60),
        (right_eye_rect.centerx, elbow_y),
        (right_eye_rect.centerx, right_eye_rect.top),
    ], 5)

    # Kabel tengah V-shape penghubung dua mata
    pygame.draw.lines(surface, BLACK, False, [
        (left_eye_rect.right - 10,  left_eye_rect.centery),
        (center_x,                   left_eye_rect.centery + 30),
        (right_eye_rect.left + 10, right_eye_rect.centery),
    ], 5)


# ══════════════════════════════════════════════════════════════════════════════
# ORNAMEN BINTANG
# ══════════════════════════════════════════════════════════════════════════════

def draw_star(
    surface: pygame.Surface,
    color: tuple,
    x: int,
    y: int,
    size: int,
) -> None:
    """Gambar bintang 8-titik (digunakan di ekspresi shy dan happier)."""
    half  = size // 2
    inner = size // 5
    points = [
        (x,          y - half),
        (x + inner,  y - inner),
        (x + half,   y),
        (x + inner,  y + inner),
        (x,          y + half),
        (x - inner,  y + inner),
        (x - half,   y),
        (x - inner,  y - inner),
    ]
    pygame.draw.polygon(surface, color, points)
