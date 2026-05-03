"""
Robot Face - Ekspresi "TALKING STATE" (1024x600)
======================================================
- SACCADE READY: Glint cahaya mata mendukung pup_ox dan pup_oy.
- INTERAKTIF: Tekan SPASI untuk toggle bicara / diam.
"""

import pygame
import sys
import math
import random

# --- 1. Inisialisasi ---
pygame.init()
WIDTH, HEIGHT = 1024, 600  # RESOLUSI NATIVE
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Robot Face - TALKING STATE (Tekan SPASI)")

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


# --- 4. PRE-RENDER & PRE-CALCULATE (no REDUNDAN) ---

# A. Pre-Render Eye Gradient
def create_base_gradient(w, h):
    gradient_tiny = pygame.Surface((1, 2))
    gradient_tiny.fill(EYE_TOP, (0, 0, 1, 1))    
    gradient_tiny.fill(EYE_BOTTOM, (0, 1, 1, 1)) 
    return pygame.transform.smoothscale(gradient_tiny, (w, h))

PRE_RENDERED_EYE_GRADIENT = create_base_gradient(eye_width, eye_height)

# B. Pre-Calculate Bibir Atas (Karena bibir atas diam saat bicara)
mouth_w = 320        # Diperlebar
mouth_top_y = 420    
curve_top_sag = 30   
steps = 60 

STATIC_TOP_POINTS = []
for i in range(steps + 1):
    t = i / steps
    px = (center_x - mouth_w // 2) + (t * mouth_w)
    py = mouth_top_y + (curve_top_sag * 4 * t * (1 - t)) 
    STATIC_TOP_POINTS.append((px, py))


# --- 5. FUNGSI GAMBAR ---

# DITAMBAHKAN: pup_ox & pup_oy untuk Saccades
def draw_eye_gradient(surface, rect, pup_ox=0, pup_oy=0):
    pygame.draw.ellipse(surface, BLACK, rect.inflate(12, 12))

    eye_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(eye_surf, (255, 255, 255), (0, 0, rect.width, rect.height))
    eye_surf.blit(PRE_RENDERED_EYE_GRADIENT, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(eye_surf, rect.topleft)
    
    # Glints bergerak mengikuti pup_ox & pup_oy
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

# Status Robot
is_talking = False      
talk_time = 0 

# Status Kedip
blink_state = "closing" 
blink_progress = 0.0    
blink_speed = 0.15      
last_blink_time = pygame.time.get_ticks()
next_blink_interval = random.randint(2000, 5000)

while running:
    # --- EVENT HANDLING ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        # TEKAN SPASI UNTUK TOGGLE BICARA / DIAM
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                is_talking = not is_talking 
                print(f"Status Bicara: {is_talking}")

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

    # 1. KABEL STATIS
    elbow_y = left_eye_rect.top - 50 
    pygame.draw.lines(screen, BLACK, False, [(-20, 60), (left_eye_rect.centerx, elbow_y), (left_eye_rect.centerx, left_eye_rect.top)], 5)
    pygame.draw.lines(screen, BLACK, False, [(WIDTH + 20, 60), (right_eye_rect.centerx, elbow_y), (right_eye_rect.centerx, right_eye_rect.top)], 5)
    pygame.draw.lines(screen, BLACK, False, [
        (left_eye_rect.right - 10, left_eye_rect.centery),
        (center_x, left_eye_rect.centery + 30),
        (right_eye_rect.left + 10, right_eye_rect.centery)
    ], 5)

    # 2. MATA (Saccade Ready)
    draw_eye_gradient(screen, left_eye_rect, pup_ox=0, pup_oy=0)
    draw_eye_gradient(screen, right_eye_rect, pup_ox=0, pup_oy=0)
    draw_eyelid(screen, left_eye_rect, blink_progress)
    draw_eyelid(screen, right_eye_rect, blink_progress)

    # ==========================================
    # BAGIAN 3: LOGIKA MULUT DINAMIS (BICARA)
    # ==========================================
    
    default_depth = 140  
    
    if is_talking:
        talk_time += 1
        wave = math.sin(talk_time * 0.15) # Kecepatan buka tutup dinaikkan sedikit agar lebih natural
        current_depth = 100 + (wave * 60) 
        
        if current_depth < 30: current_depth = 30 # Batas minimal mulut tertutup
        curve_bottom_depth = current_depth
    else:
        curve_bottom_depth = default_depth

    # Hitung Kurva Bawah (Dinamis)
    bottom_points = []
    a = mouth_w / 2 
    b = curve_bottom_depth 

    for i in range(steps + 1):
        t = i / steps
        px = (center_x - mouth_w // 2) + (t * mouth_w)
        dx = px - center_x
        inside_sqrt = max(0, 1 - (dx / a)**2) 
        offset_y = b * math.sqrt(inside_sqrt)
        py = mouth_top_y + offset_y
        bottom_points.append((px, py))

    # Gabungkan bibir atas (statis) dan bibir bawah (dinamis)
    mouth_points = STATIC_TOP_POINTS + list(reversed(bottom_points))

    # --- RENDERING MULUT (Local Masking Anti-Offside) ---
    
    # 1. Bounding box kanvas mulut
    box_w = mouth_w + 10
    box_h = int(curve_bottom_depth + 40) # Dinamis mengikuti seberapa lebar mulut terbuka
    box_x = center_x - mouth_w // 2
    box_y = mouth_top_y

    # Translasi titik poligon ke lokal
    local_mouth_points = [(px - box_x, py - box_y) for px, py in mouth_points]

    # 2. Gambar dasar rongga gelap di layar utama
    pygame.draw.polygon(screen, MOUTH_DARK, mouth_points)

    # 3. Kanvas memori kecil (seukuran bounding box)
    mouth_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_surf, (255, 255, 255, 255), local_mouth_points)

    # 4. Logika posisi lidah (Ikut naik-turun saat mulut bergerak)
    tongue_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    tongue_base_y = 60
    if curve_bottom_depth < 70: tongue_base_y += 30 # Lidah turun kalau mulut mengecil
        
    local_tongue_rect = pygame.Rect(20, tongue_base_y, mouth_w - 40, 110)
    pygame.draw.ellipse(tongue_surf, TONGUE, local_tongue_rect)

    # 5. Masking
    mouth_surf.blit(tongue_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    screen.blit(mouth_surf, (box_x, box_y))

    # 6. Outline
    pygame.draw.polygon(screen, BLACK, mouth_points, 8)
    pygame.draw.aalines(screen, BLACK, True, mouth_points)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()