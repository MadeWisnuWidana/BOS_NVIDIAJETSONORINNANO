"""
Robot Face - Ekspresi "SHY / KAWAII 'w'" (1024x600)
======================================================
- ANIMASI: Continuous Natural Blinking aktif.
"""

import pygame
import sys
import math
import random 

# --- 1. Inisialisasi ---
pygame.init()
WIDTH, HEIGHT = 1024, 600  # RESOLUSI NATIVE
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Robot Face - SHY 'w' (Optimized)")

# --- 2. Warna ---
BG_COLOR    = (205, 215, 225) 
BLACK       = (0, 0, 0)
HIGHLIGHT   = (255, 255, 255) 
BLUSH_COLOR = (255, 180, 200) 

EYE_TOP     = (80, 70, 150)
EYE_BOTTOM  = (0, 0, 0)

# --- 3. PARAMETER UNIVERSAL 1024x600 ---
center_x = WIDTH // 2
eye_y = 220
eye_width = 130
eye_height = 160
dist_from_center = 170

left_eye_rect = pygame.Rect(center_x - dist_from_center - eye_width, eye_y, eye_width, eye_height)
right_eye_rect = pygame.Rect(center_x + dist_from_center, eye_y, eye_width, eye_height)


# --- 4. PRE-RENDER LAYER (ANTI REDUNDAN) ---

# A. Pre-Render Eye Gradient
def create_base_gradient(w, h):
    gradient_tiny = pygame.Surface((1, 2))
    gradient_tiny.fill(EYE_TOP, (0, 0, 1, 1))    
    gradient_tiny.fill(EYE_BOTTOM, (0, 1, 1, 1)) 
    return pygame.transform.smoothscale(gradient_tiny, (w, h))

PRE_RENDERED_EYE_GRADIENT = create_base_gradient(eye_width, eye_height)

# B. Pre-Render Blush On (Sangat menghemat RAM)
blush_w, blush_h = 100, 60 
PRE_RENDERED_BLUSH = pygame.Surface((blush_w, blush_h), pygame.SRCALPHA)
pygame.draw.ellipse(PRE_RENDERED_BLUSH, (*BLUSH_COLOR, 150), (0, 0, blush_w, blush_h))


# --- 5. FUNGSI GAMBAR ---

def draw_star(surface, color, x, y, size):
    half = size // 2
    inner = size // 5 
    points = [
        (x, y - half), (x + inner, y - inner),
        (x + half, y), (x + inner, y + inner),
        (x, y + half), (x - inner, y + inner),
        (x - half, y), (x - inner, y - inner)
    ]
    pygame.draw.polygon(surface, color, points)

def draw_eye_gradient_with_sparkles(surface, rect, pup_ox=0, pup_oy=0):
    # Outline Hitam
    pygame.draw.ellipse(surface, BLACK, rect.inflate(12, 12))
    
    # Blit Pre-rendered Gradient
    eye_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(eye_surf, (255, 255, 255), (0, 0, rect.width, rect.height))
    eye_surf.blit(PRE_RENDERED_EYE_GRADIENT, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(eye_surf, rect.topleft)
    
    # Ornamen Bintang (Bergeser mengikuti pup_ox & pup_oy)
    glint_x = rect.left + int(rect.width * 0.35) + pup_ox
    glint_y = rect.top + int(rect.height * 0.3) + pup_oy
    
    draw_star(surface, HIGHLIGHT, glint_x, glint_y, 45) 
    pygame.draw.circle(surface, HIGHLIGHT, (glint_x + 25, glint_y + 25), 6)
    pygame.draw.circle(surface, (150, 150, 255), (glint_x - 15, glint_y + 15), 4)

def draw_eyelid(surface, rect, progress):
    if progress <= 0: return 
    lid_height = rect.height * progress
    cover_rect = pygame.Rect(rect.left - 6, rect.top - 6, rect.width + 12, lid_height + 6)
    pygame.draw.rect(surface, BG_COLOR, cover_rect)
    line_y = rect.top + lid_height
    if line_y > rect.bottom: line_y = rect.bottom
    pygame.draw.line(surface, BLACK, (rect.left - 6, line_y), (rect.right + 6, line_y), 6)


# --- 6. LOOP UTAMA ---
running = True
clock = pygame.time.Clock()

blink_state = "closing" 
blink_progress = 0.0    
blink_speed = 0.15      

last_blink_time = pygame.time.get_ticks()
next_blink_wait = random.randint(2000, 5000) 

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill(BG_COLOR)
    current_time = pygame.time.get_ticks()

    # --- LOGIKA KEDIP (Continuous) ---
    if blink_state == "closing":
        blink_progress += blink_speed
        if blink_progress >= 1.0:
            blink_progress = 1.0
            blink_state = "opening"
    elif blink_state == "opening":
        blink_progress -= blink_speed
        if blink_progress <= 0.0:
            blink_progress = 0.0
            blink_state = "idle"
            last_blink_time = current_time
            next_blink_wait = random.randint(2000, 6000)
    elif blink_state == "idle":
        if current_time - last_blink_time > next_blink_wait:
            blink_state = "closing"

    # 1. KABEL STATIS
    elbow_y = left_eye_rect.top - 50 
    pygame.draw.lines(screen, BLACK, False, [(-20, 60), (left_eye_rect.centerx, elbow_y), (left_eye_rect.centerx, left_eye_rect.top)], 5)
    pygame.draw.lines(screen, BLACK, False, [(WIDTH + 20, 60), (right_eye_rect.centerx, elbow_y), (right_eye_rect.centerx, right_eye_rect.top)], 5)
    pygame.draw.lines(screen, BLACK, False, [
        (left_eye_rect.right - 10, left_eye_rect.centery),
        (center_x, left_eye_rect.centery + 30),
        (right_eye_rect.left + 10, right_eye_rect.centery)
    ], 5)

    # 2. BLUSH ON (Tinggal tempel, posisi dinamis mengikuti mata)
    screen.blit(PRE_RENDERED_BLUSH, (left_eye_rect.centerx - blush_w//2, left_eye_rect.bottom + 20))
    screen.blit(PRE_RENDERED_BLUSH, (right_eye_rect.centerx - blush_w//2, right_eye_rect.bottom + 20))

    # 3. MATA SPARKLES & KELOPAK (Saccade Ready)
    draw_eye_gradient_with_sparkles(screen, left_eye_rect, pup_ox=0, pup_oy=0)
    draw_eye_gradient_with_sparkles(screen, right_eye_rect, pup_ox=0, pup_oy=0)
    
    draw_eyelid(screen, left_eye_rect, blink_progress)
    draw_eyelid(screen, right_eye_rect, blink_progress)

    # 4. MULUT MALU (SHY 'w' MOUTH)
    mouth_y = 440          
    arc_radius = 40        # Diperbesar untuk layar 1024
    line_thickness = 8     

    rect_left_arc = pygame.Rect(center_x - (arc_radius * 2), mouth_y, arc_radius * 2, arc_radius * 2)
    rect_right_arc = pygame.Rect(center_x, mouth_y, arc_radius * 2, arc_radius * 2)

    # Karena mulut tidak ikut berkedip (tidak gepeng), langsung digambar saja tanpa masking
    pygame.draw.arc(screen, BLACK, rect_left_arc, math.pi, 0, line_thickness)
    pygame.draw.arc(screen, BLACK, rect_right_arc, math.pi, 0, line_thickness)

    # Ujung Kiri
    pygame.draw.circle(screen, BLACK, (center_x - (arc_radius * 2) + 2, mouth_y + arc_radius), line_thickness//2)
    # Ujung Tengah
    pygame.draw.circle(screen, BLACK, (center_x, mouth_y + arc_radius), line_thickness//2)
    # Ujung Kanan
    pygame.draw.circle(screen, BLACK, (center_x + (arc_radius * 2) - 2, mouth_y + arc_radius), line_thickness//2)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()