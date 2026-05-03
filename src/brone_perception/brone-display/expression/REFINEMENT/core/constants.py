"""
core/constants.py
=================
Semua konstanta warna, parameter layout layar, dan posisi mata
yang digunakan bersama oleh seluruh ekspresi robot.
"""

import pygame

# ── Resolusi ──────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1024, 600   # Resolusi native Jetson display

# ── Palet Warna ───────────────────────────────────────────────────────────────
BG_COLOR    = (205, 215, 225)   # Abu-abu muda (latar belakang)
BLACK       = (0, 0, 0)
WHITE       = (255, 255, 255)
HIGHLIGHT   = (240, 245, 255)   # Putih kebiruan (glint mata)
HIGHLIGHT_W = (255, 255, 255)   # Putih murni (cry / shy)
MOUTH_DARK  = (40, 40, 40)      # Rongga mulut

EYE_TOP     = (80, 70, 150)     # Ungu gelap (gradasi atas mata)
EYE_BOTTOM  = (0, 0, 0)         # Hitam (gradasi bawah mata)

TONGUE      = (230, 130, 100)   # Warna lidah
BLUSH_COLOR = (255, 180, 200)   # Pipi memerah

# ── Warna Ekspresi Cry ────────────────────────────────────────────────────────
TEAR_STREAM_COLOR = (170, 230, 255)   # Aliran air mata
EYE_WATER         = (130, 200, 255)   # Air di dalam mata
EYE_BASE_COLOR    = (40, 30, 70)      # Dasar mata ungu gelap

# ── Warna Ekspresi Load (mata bergaya) ────────────────────────────────────────
COLOR_BASE_TOP    = (80, 70, 150)
COLOR_BASE_BOTTOM = (10, 10, 30)
COLOR_SCLERA      = (230, 235, 240)
COLOR_IRIS        = (45, 75, 60)
COLOR_PUPIL       = (210, 230, 220)

# ── Layout Mata (Parameter Universal 1024×600) ────────────────────────────────
center_x         = WIDTH // 2
eye_y            = 220
eye_width        = 130
eye_height       = 160
dist_from_center = 170

def make_eye_rects():
    """Kembalikan (left_eye_rect, right_eye_rect) berdasarkan parameter universal."""
    left  = pygame.Rect(center_x - dist_from_center - eye_width, eye_y, eye_width, eye_height)
    right = pygame.Rect(center_x + dist_from_center, eye_y, eye_width, eye_height)
    return left, right
