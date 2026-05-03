import pygame
import sys
import math
import random

# --- 1. Inisialisasi ---
pygame.init()
WIDTH, HEIGHT = 1024, 600  # RESOLUSI NATIVE YANG BENAR
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Robot Face - LOAD (Fully Optimized & Saccade Ready)")

# --- 2. Warna ---
BG_COLOR    = (205, 215, 225) 
BLACK       = (0, 0, 0)
MOUTH_DARK  = (40, 40, 40)
TONGUE      = (230, 130, 100)

COLOR_BASE_TOP    = (80, 70, 150)    
COLOR_BASE_BOTTOM = (10, 10, 30)     
COLOR_SCLERA      = (230, 235, 240)  
COLOR_IRIS        = (45, 75, 60)     
COLOR_PUPIL       = (210, 230, 220)  

# --- 3. PARAMETER UNIVERSAL 1024x600 ---
center_x = WIDTH // 2
eye_y = 220
eye_width = 130
eye_height = 160
dist_from_center = 170

# Pusat rotasi & posisi mata
left_eye_center = (center_x - dist_from_center - eye_width // 2, eye_y + eye_height // 2)
right_eye_center = (center_x + dist_from_center + eye_width // 2, eye_y + eye_height // 2)

left_eye_rect = pygame.Rect(0, 0, eye_width, eye_height)
left_eye_rect.center = left_eye_center
right_eye_rect = pygame.Rect(0, 0, eye_width, eye_height)
right_eye_rect.center = right_eye_center

# --- 4. PRE-RENDER LAYER (BEBAS REDUNDANSI) ---
# Dihitung HANYA 1X saat start
def create_base_gradient(w, h):
    surface = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        ratio = max(0, min(1, y / h))
        r = COLOR_BASE_TOP[0] * (1 - ratio) + COLOR_BASE_BOTTOM[0] * ratio
        g = COLOR_BASE_TOP[1] * (1 - ratio) + COLOR_BASE_BOTTOM[1] * ratio
        b = COLOR_BASE_TOP[2] * (1 - ratio) + COLOR_BASE_BOTTOM[2] * ratio
        pygame.draw.line(surface, (r, g, b), (0, y), (w, y))
    return surface

PRE_RENDERED_BASE = create_base_gradient(eye_width, eye_height)

# --- 5. FUNGSI GAMBAR ---

def draw_rotated_layered_eye(target_surface, dest_rect, gaze_dir, angle, pup_ox=0, pup_oy=0):
    w, h = dest_rect.width, dest_rect.height
    diagonal = int(math.sqrt(w**2 + h**2)) + 10
    canvas_size = (diagonal, diagonal)
    
    canvas = pygame.Surface(canvas_size, pygame.SRCALPHA)
    cx, cy = diagonal // 2, diagonal // 2
    
    # Tempel gradient yang sudah di-render 
    content = pygame.Surface((w, h), pygame.SRCALPHA)
    content.blit(PRE_RENDERED_BASE, (0, 0))

    base_shift = 25 * gaze_dir 
    
    # Sclera
    sclera_w, sclera_h = w * 0.75, h * 0.85
    sclera_x = (w - sclera_w) / 2 + (base_shift * 0.8)
    pygame.draw.ellipse(content, COLOR_SCLERA, (sclera_x, (h - sclera_h)/2 + 5, sclera_w, sclera_h))

    # Iris
    iris_w, iris_h = w * 0.55, h * 0.65
    iris_x = (w - iris_w) / 2 + (base_shift * 1.0)
    pygame.draw.ellipse(content, COLOR_IRIS, (iris_x, (h - iris_h)/2 + 8, iris_w, iris_h))

    # Pupil (DENGAN PENAMBAHAN PARAMETER pup_ox & pup_oy UNTUK SACCADES)
    pupil_w, pupil_h = w * 0.30, h * 0.35
    pupil_x = (w - pupil_w) / 2 + (base_shift * 1.2) + pup_ox
    pupil_y = (h - pupil_h) / 2 + 10 + pup_oy
    pygame.draw.ellipse(content, COLOR_PUPIL, (pupil_x, pupil_y, pupil_w, pupil_h))

    # Masking Ellipse
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(mask, (255, 255, 255), (0, 0, w, h))
    content.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    
    # Blit ke kanvas rotasi
    canvas.blit(content, (cx - w//2, cy - h//2))
    pygame.draw.ellipse(canvas, BLACK, (cx - w//2, cy - h//2, w, h), 6)

    # Rotasi & Render Akhir
    if angle != 0:
        canvas = pygame.transform.rotate(canvas, angle)
    
    new_rect = canvas.get_rect(center=dest_rect.center)
    target_surface.blit(canvas, new_rect.topleft)

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

    # 1. KABEL
    elbow_y = left_eye_rect.top - 50 
    pygame.draw.lines(screen, BLACK, False, [(-20, 60), (left_eye_rect.centerx, elbow_y), (left_eye_rect.centerx, left_eye_rect.top + 20)], 5)
    pygame.draw.lines(screen, BLACK, False, [(WIDTH + 20, 60), (right_eye_rect.centerx, elbow_y), (right_eye_rect.centerx, right_eye_rect.top + 20)], 5)
    pygame.draw.lines(screen, BLACK, False, [
        (left_eye_rect.right - 10, left_eye_rect.centery),
        (center_x, left_eye_rect.centery + 30),
        (right_eye_rect.left + 10, right_eye_rect.centery)
    ], 5)

    # 2. MATA ASIMETRIS (Saccade Ready)
    gaze_direction = -1 
    # pup_ox & pup_oy diisi 0, nanti tinggal diubah pakai FSM Saccades
    draw_rotated_layered_eye(screen, left_eye_rect, gaze_direction, 0, pup_ox=0, pup_oy=0)
    draw_rotated_layered_eye(screen, right_eye_rect, gaze_direction, 10, pup_ox=0, pup_oy=0)

    # 3. KELOPAK MATA
    draw_eyelid(screen, left_eye_rect, blink_progress)
    draw_eyelid(screen, right_eye_rect, blink_progress)

    # 4. MULUT SQUASH & STRETCH
    base_mouth_w = 220  
    base_mouth_h = 130
    
    current_mouth_h = base_mouth_h * (1.0 - blink_progress)
    current_mouth_w = base_mouth_w + (blink_progress * 40) 
    if current_mouth_h < 6: current_mouth_h = 6

    mouth_rect = pygame.Rect(0, 0, current_mouth_w, current_mouth_h)
    mouth_rect.center = (center_x, 420 + base_mouth_h//2) 

    if current_mouth_h > 10:
        pygame.draw.ellipse(screen, MOUTH_DARK, mouth_rect)
        
        # Clipping Lidah  aman memori
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