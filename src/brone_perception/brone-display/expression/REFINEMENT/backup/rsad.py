"""
Robot Face - Ekspresi "NEUTRAL/SAD MOUTH" (1024x600) - PROPORTIONAL FIX
======================================================
- Menggunakan parameter universal layar 1024x600.
"""

import pygame
import sys
import math
import random 

# --- 1. Inisialisasi ---
pygame.init()
WIDTH, HEIGHT = 1024, 600  # RESOLUSI NATIVE
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Robot Face - NEUTRAL/SAD MOUTH (Proportional)")

# --- 2. Warna ---
BG_COLOR    = (205, 215, 225) 
BLACK       = (0, 0, 0)
HIGHLIGHT   = (240, 245, 255)
MOUTH_DARK  = (40, 40, 40)
TONGUE      = (230, 130, 100)

EYE_TOP     = (80, 70, 150)
EYE_BOTTOM  = (0, 0, 0)

# --- 3. PARAMETER 1024x600 ---
center_x = WIDTH // 2
eye_y = 220
eye_width = 130
eye_height = 160
dist_from_center = 170

left_eye_rect = pygame.Rect(center_x - dist_from_center - eye_width, eye_y, eye_width, eye_height)
right_eye_rect = pygame.Rect(center_x + dist_from_center, eye_y, eye_width, eye_height)


# --- 4. PRE-RENDER & PRE-CALCULATE noREDUNDAN) ---

# A. Pre-Render Eye Gradient
def create_base_gradient(w, h):
    gradient_tiny = pygame.Surface((1, 2))
    gradient_tiny.fill(EYE_TOP, (0, 0, 1, 1))    
    gradient_tiny.fill(EYE_BOTTOM, (0, 1, 1, 1)) 
    return pygame.transform.smoothscale(gradient_tiny, (w, h))

PRE_RENDERED_EYE_GRADIENT = create_base_gradient(eye_width, eye_height)

# B. Pre-Calculate Mulut Melengkung Bawah 
mouth_w = 180        
mouth_h = 75         # Kedalaman lengkungan disesuaikan
base_y = 480         

STATIC_MOUTH_POINTS = []
steps = 80
radius_x = mouth_w / 2
radius_y = mouth_h

# Kurva Atas
for i in range(steps + 1):
    t = i / steps
    px = (center_x - mouth_w // 2) + (t * mouth_w)
    dx = px - center_x
    inside_sqrt = max(0, 1 - (dx / radius_x)**2)
    offset_y = radius_y * math.sqrt(inside_sqrt)
    py = base_y - offset_y
    STATIC_MOUTH_POINTS.append((px, py))

# Kurva Bawah 
bottom_sag = 10  
for i in range(steps, -1, -1):
    t = i / steps
    px = (center_x - mouth_w // 2) + (t * mouth_w)
    py = base_y - (bottom_sag * math.sin(t * math.pi))
    STATIC_MOUTH_POINTS.append((px, py))

# Bounding Box Mulut (Untuk Local Masking)
box_w = mouth_w + 10
box_h = mouth_h + bottom_sag + 10
box_x = center_x - mouth_w // 2
box_y = base_y - mouth_h

# Translasi Titik ke Koordinat Lokal Surface Mini
LOCAL_MOUTH_POINTS = [(px - box_x, py - box_y) for px, py in STATIC_MOUTH_POINTS]


# --- 5. FUNGSI GAMBAR ---

def draw_eye_gradient(surface, rect, pup_ox=0, pup_oy=0):
    pygame.draw.ellipse(surface, BLACK, rect.inflate(12, 12))

    eye_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(eye_surf, (255, 255, 255), (0, 0, rect.width, rect.height))
    eye_surf.blit(PRE_RENDERED_EYE_GRADIENT, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(eye_surf, rect.topleft)
    
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
    
    # KELOPAK MATA
    draw_eyelid(screen, left_eye_rect, blink_progress)
    draw_eyelid(screen, right_eye_rect, blink_progress)

    # 3. MULUT (Proporsi Imut & Masking Anti-Offside)
    pygame.draw.polygon(screen, MOUTH_DARK, STATIC_MOUTH_POINTS)

    # Kanvas Memori Mini 
    mouth_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_surf, (255, 255, 255, 255), LOCAL_MOUTH_POINTS)
    
    # Lidah ( hanya 60% dari lebar mulut)
    tongue_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    tongue_fill_height = 35 
    tongue_w = mouth_w * 0.6 
    
    # Posisikan lidah di tengah dasar mulut
    local_tongue_rect = pygame.Rect(box_w//2 - tongue_w//2, box_h - tongue_fill_height - 5, tongue_w, tongue_fill_height * 2)
    pygame.draw.ellipse(tongue_surf, TONGUE, local_tongue_rect)
    
    # Masking 
    mouth_surf.blit(tongue_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    screen.blit(mouth_surf, (box_x, box_y))

    # Outline
    pygame.draw.polygon(screen, BLACK, STATIC_MOUTH_POINTS, 8)
    pygame.draw.aalines(screen, BLACK, True, STATIC_MOUTH_POINTS)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()