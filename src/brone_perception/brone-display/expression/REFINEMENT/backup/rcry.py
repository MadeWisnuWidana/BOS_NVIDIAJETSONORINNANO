"""
Robot Face - Ekspresi "CRY" (1024x600)
======================================================
- Menggunakan parameter universal layar 1024x600.
- SACCADE READY: Glint dan air mata mendukung pup_ox dan pup_oy.
- BLINK READY: Tetap bisa berkedip natural sambil menangis.
"""

import pygame
import sys
import math
import random

# --- 1. Inisialisasi ---
pygame.init()
WIDTH, HEIGHT = 1024, 600  # RESOLUSI NATIVE
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Robot Face - CRY (Anti-Offside & Optimized)")

# --- 2. Warna ---
BG_COLOR    = (205, 215, 225) 
BLACK       = (0, 0, 0)
HIGHLIGHT   = (255, 255, 255)
MOUTH_DARK  = (40, 40, 40)
TONGUE      = (230, 130, 100) 

TEAR_STREAM_COLOR = (170, 230, 255) 
EYE_WATER         = (130, 200, 255) 
EYE_BASE_COLOR    = (40, 30, 70)     

# --- 3. PARAMETER UNIVERSAL 1024x600 ---
center_x = WIDTH // 2
eye_y = 220
eye_width = 130
eye_height = 160
dist_from_center = 170

left_eye_rect = pygame.Rect(center_x - dist_from_center - eye_width, eye_y, eye_width, eye_height)
right_eye_rect = pygame.Rect(center_x + dist_from_center, eye_y, eye_width, eye_height)

# --- 4. PRE-CALCULATE & PRE-RENDER (ANTI REDUNDAN) ---

# A. Pre-Render Eye Mask (Untuk memotong gelombang air)
EYE_MASK_SURF = pygame.Surface((eye_width, eye_height), pygame.SRCALPHA)
pygame.draw.ellipse(EYE_MASK_SURF, (255, 255, 255, 255), (0, 0, eye_width, eye_height))

# B. Pre-Calculate Titik Mulut Sedih
mouth_w = 200        
mouth_h = 100        
base_y = 520         

STATIC_MOUTH_POINTS = []
steps = 60

# Kurva Atas (Melengkung tajam ke atas seperti bukit tinggi)
for i in range(steps + 1):
    t = i / steps
    px = (center_x - mouth_w // 2) + (t * mouth_w)
    py = base_y - (mouth_h * 4 * t * (1 - t)) # Parabola ke atas
    STATIC_MOUTH_POINTS.append((px, py))

# Kurva Bawah (Melengkung sedikit ke atas, membentuk rongga)
bottom_points = []
for i in range(steps + 1):
    t = i / steps
    px = (center_x - mouth_w // 2) + (t * mouth_w)
    py = base_y - (20 * 4 * t * (1 - t)) # Parabola landai ke atas
    bottom_points.append((px, py))

STATIC_MOUTH_POINTS.extend(reversed(bottom_points))

# Bounding Box Mulut (Untuk Local Masking)
box_x = center_x - mouth_w // 2
box_y = base_y - mouth_h
box_w = mouth_w
box_h = mouth_h

LOCAL_MOUTH_POINTS = [(px - box_x, py - box_y) for px, py in STATIC_MOUTH_POINTS]


# --- 5. FUNGSI GAMBAR ---

def draw_purple_eye_with_wave(surface, rect, time_val, pup_ox=0, pup_oy=0):
    pygame.draw.ellipse(surface, EYE_BASE_COLOR, rect)
    
    # Wave Surface
    wave_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    water_points = []
    water_level = rect.height * 0.55 
    
    for x in range(rect.width):
        wave_height = 5 * math.sin(0.15 * x + time_val) 
        water_points.append((x, water_level + wave_height + pup_oy)) 
    
    water_points.append((rect.width, rect.height))
    water_points.append((0, rect.height))
    pygame.draw.polygon(wave_surf, EYE_WATER, water_points)
    
    # Blit mask gelombang
    wave_surf.blit(EYE_MASK_SURF, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(wave_surf, rect.topleft)

    pygame.draw.ellipse(surface, BLACK, rect, 6)

    # Glints siap digeser (Saccades)
    big_glint_pos = (rect.left + 35 + pup_ox, rect.top + 45 + pup_oy)
    pygame.draw.circle(surface, HIGHLIGHT, big_glint_pos, 22)
    
    small_glint_pos = (rect.left + 55 + pup_ox, rect.top + 80 + pup_oy)
    pygame.draw.circle(surface, HIGHLIGHT, small_glint_pos, 6)

def draw_cartoon_stream_slow(surface, start_x, start_y, time_val):
    stream_points = []
    width_top = 40      
    width_bottom = 50   
    
    # Optimized steps = 10 
    for y in range(start_y, HEIGHT, 10): 
        prog = (y - start_y) / (HEIGHT - start_y) 
        current_w = width_top + (width_bottom - width_top) * prog
        wiggle = math.sin(y * 0.05 + time_val) * 4
        x = start_x - (current_w / 2) + wiggle
        stream_points.append((x, y))
        
    for y in range(HEIGHT, start_y, -10):
        prog = (y - start_y) / (HEIGHT - start_y)
        current_w = width_top + (width_bottom - width_top) * prog
        wiggle = math.sin(y * 0.05 + time_val) * 4
        x = start_x + (current_w / 2) + wiggle
        stream_points.append((x, y))
        
    pygame.draw.polygon(surface, TEAR_STREAM_COLOR, stream_points)
    
    pygame.draw.circle(surface, TEAR_STREAM_COLOR, (start_x - 15, start_y + 5), 10)
    pygame.draw.circle(surface, TEAR_STREAM_COLOR, (start_x, start_y + 8), 12)
    pygame.draw.circle(surface, TEAR_STREAM_COLOR, (start_x + 15, start_y + 5), 10)

    for i in range(3):
        offset = i * 250 
        drop_speed = 25 
        drop_y = start_y + ((time_val * drop_speed + offset) % (HEIGHT - start_y + 100))
        if drop_y < HEIGHT:
            h_rect = pygame.Rect(start_x - 8, drop_y, 16, 35)
            pygame.draw.ellipse(surface, HIGHLIGHT, h_rect)

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

time_counter = 0        
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
    time_counter += 0.1 

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

    # 2. ALIRAN AIR MATA (STREAM)
    draw_cartoon_stream_slow(screen, left_eye_rect.centerx, left_eye_rect.bottom - 20, time_counter)
    draw_cartoon_stream_slow(screen, right_eye_rect.centerx, right_eye_rect.bottom - 20, time_counter)

    # 3. MATA UNGU (Saccade Ready)
    draw_purple_eye_with_wave(screen, left_eye_rect, time_counter, pup_ox=0, pup_oy=0)
    draw_purple_eye_with_wave(screen, right_eye_rect, time_counter + 2, pup_ox=0, pup_oy=0)

    # 4. KELOPAK MATA
    draw_eyelid(screen, left_eye_rect, blink_progress)
    draw_eyelid(screen, right_eye_rect, blink_progress)

    # 5. MULUT SEDIH (Anime Wailing)
    pygame.draw.polygon(screen, MOUTH_DARK, STATIC_MOUTH_POINTS)

    # Kanvas memori kecil
    mouth_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_surf, (255, 255, 255, 255), LOCAL_MOUTH_POINTS)

    # Gambar Lidah (Membulat di dasar mulut)
    # tongue_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    # tongue_rect = pygame.Rect(box_w//2 - 40, box_h - 35, 80, 50) 
    # pygame.draw.ellipse(tongue_surf, TONGUE, tongue_rect)

    mouth_surf.blit(tongue_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    screen.blit(mouth_surf, (box_x, box_y))

    # Outline
    pygame.draw.polygon(screen, BLACK, STATIC_MOUTH_POINTS, 8)
    pygame.draw.aalines(screen, BLACK, True, STATIC_MOUTH_POINTS)

    # Kanvas memori kecil (Hanya sebesar kotak mulut)
    mouth_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_surf, (255, 255, 255, 255), LOCAL_MOUTH_POINTS)

    # Gambar Lidah relatif terhadap kanvas kecil
    # tongue_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    # tongue_rect = pygame.Rect(0, box_h - 45, box_w, 80) 
    # pygame.draw.ellipse(tongue_surf, TONGUE, tongue_rect)

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