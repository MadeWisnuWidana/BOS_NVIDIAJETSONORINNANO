"""
Robot Face - Ekspresi "OVAL/SURPRISED" (1024x600)
======================================================
- SACCADE READY: Glint cahaya mata mendukung pup_ox dan pup_oy.
"""

import pygame
import sys
import math
import random 

# --- 1. Inisialisasi ---
pygame.init()
WIDTH, HEIGHT = 1024, 600  # RESOLUSI NATIVE
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Robot Face - OVAL (Optimized & Saccade Ready)")

# --- 2. Warna ---
BG_COLOR    = (205, 215, 225) 
BLACK       = (0, 0, 0)
HIGHLIGHT   = (240, 245, 255)
MOUTH_DARK  = (40, 40, 40)
TONGUE      = (230, 130, 100)

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
# Dihitung 1X saja sebelum loop dimulai
def create_base_gradient(w, h):
    gradient_tiny = pygame.Surface((1, 2))
    gradient_tiny.fill(EYE_TOP, (0, 0, 1, 1))    
    gradient_tiny.fill(EYE_BOTTOM, (0, 1, 1, 1)) 
    return pygame.transform.smoothscale(gradient_tiny, (w, h))

PRE_RENDERED_EYE_GRADIENT = create_base_gradient(eye_width, eye_height)

# --- 5. FUNGSI GAMBAR ---

# DITAMBAHKAN: pup_ox & pup_oy untuk fitur melirik (Saccades)
def draw_eye_gradient(surface, rect, pup_ox=0, pup_oy=0):
    # 1. Outline Hitam Tebal
    pygame.draw.ellipse(surface, BLACK, rect.inflate(12, 12))

    # 2. Tempel Gradasi Pre-Rendered (Sangat hemat RAM)
    eye_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(eye_surf, (255, 255, 255), (0, 0, rect.width, rect.height))
    eye_surf.blit(PRE_RENDERED_EYE_GRADIENT, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(eye_surf, rect.topleft)
    
    # 3. Highlights (Bergerak mengikuti pup_ox & pup_oy)
    glint_x = rect.left + int(rect.width * 0.3) + pup_ox
    glint_y = rect.top + int(rect.height * 0.25) + pup_oy
    
    pygame.draw.circle(surface, HIGHLIGHT, (glint_x, glint_y), int(rect.width * 0.18))
    pygame.draw.circle(surface, EYE_TOP, (glint_x + 8, glint_y + 8), int(rect.width * 0.08))

    small_glint_x = glint_x - 5
    small_glint_y = glint_y + int(rect.height * 0.3)
    pygame.draw.circle(surface, HIGHLIGHT, (small_glint_x, small_glint_y), int(rect.width * 0.05))

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
next_blink_interval = random.randint(2000, 5000)

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill(BG_COLOR)
    current_time = pygame.time.get_ticks()

    # --- LOGIKA KEDIP ---
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
            next_blink_interval = random.randint(2000, 6000)
    elif blink_state == "idle":
        if current_time - last_blink_time > next_blink_interval:
            blink_state = "closing"

    # ==========================
    # BAGIAN 1: KABEL 
    # ==========================
    elbow_y = left_eye_rect.top - 50 
    pygame.draw.lines(screen, BLACK, False, [(-20, 60), (left_eye_rect.centerx, elbow_y), (left_eye_rect.centerx, left_eye_rect.top)], 5)
    pygame.draw.lines(screen, BLACK, False, [(WIDTH + 20, 60), (right_eye_rect.centerx, elbow_y), (right_eye_rect.centerx, right_eye_rect.top)], 5)
    pygame.draw.lines(screen, BLACK, False, [
        (left_eye_rect.right - 10, left_eye_rect.centery),
        (center_x, left_eye_rect.centery + 30),
        (right_eye_rect.left + 10, right_eye_rect.centery)
    ], 5)

    # ==========================
    # BAGIAN 2: MATA (SACCADE READY)
    # ==========================
    # Bisa disisipkan pup_ox/pup_oy kalau mau melirik
    draw_eye_gradient(screen, left_eye_rect, pup_ox=0, pup_oy=0)
    draw_eye_gradient(screen, right_eye_rect, pup_ox=0, pup_oy=0)

    # KELOPAK MATA (KEDIP)
    draw_eyelid(screen, left_eye_rect, blink_progress)
    draw_eyelid(screen, right_eye_rect, blink_progress)

    # ==========================================
    # BAGIAN 3: MULUT OVAL SQUASH & STRETCH
    # ==========================================
    
    # 1. Konfigurasi Awal (Disesuaikan untuk 1024x600)
    base_mouth_w = 220  
    base_mouth_h = 160  
    
    # 2. Hitung Bentuk Mulut (Semakin merem, semakin gepeng & lebar)
    current_mouth_h = base_mouth_h * (1.0 - blink_progress)
    current_mouth_w = base_mouth_w + (blink_progress * 40) 
    
    if current_mouth_h < 6: current_mouth_h = 6

    # 3. Buat Rect Mulut
    mouth_rect = pygame.Rect(0, 0, current_mouth_w, current_mouth_h)
    mouth_rect.center = (center_x, 440) # Jaga posisi tengah di kordinat Y=440

    # 4. Gambar Mulut (Karena Elips, set_clip aman & no-offside)
    if current_mouth_h > 10:
        pygame.draw.ellipse(screen, MOUTH_DARK, mouth_rect)
        
        # Clipping Hardware (Aman & Ringan)
        clip_rect = pygame.Rect(mouth_rect.left, mouth_rect.centery, mouth_rect.width, mouth_rect.height // 2)
        screen.set_clip(clip_rect) 
        pygame.draw.ellipse(screen, TONGUE, mouth_rect)
        screen.set_clip(None)
        
        pygame.draw.ellipse(screen, BLACK, mouth_rect, 6)
    else:
        pygame.draw.line(screen, BLACK, 
                         (mouth_rect.left, mouth_rect.centery), 
                         (mouth_rect.right, mouth_rect.centery), 6)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()