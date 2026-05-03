import pygame
import sys
import math

# --- 1. Inisialisasi ---
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Robot Face - Happy Start Blink Transition")

# --- 2. Warna ---
BG_COLOR    = (205, 215, 225) 
BLACK       = (0, 0, 0)
EYE_COLOR   = (45, 40, 90)
HIGHLIGHT   = (240, 245, 255)
MOUTH_DARK  = (40, 40, 40)
TONGUE      = (230, 130, 100)

# Variabel Warna Gradasi (Sesuai kode aslimu)
EYE_TOP     = (80, 70, 150)
EYE_BOTTOM  = (0, 0, 0)

# --- 3. Fungsi Pendukung ---

def draw_eye_gradient(surface, rect):
    # (Fungsi asli kamu untuk mata happy)
    top = globals().get('EYE_TOP', (80, 70, 150))
    bottom = globals().get('EYE_BOTTOM', (0, 0, 0))
    pygame.draw.ellipse(surface, BLACK, rect.inflate(8, 8))

    gradient_tiny = pygame.Surface((1, 2))
    gradient_tiny.fill(top, (0, 0, 1, 1))    
    gradient_tiny.fill(bottom, (0, 1, 1, 1)) 
    gradient_surf = pygame.transform.smoothscale(gradient_tiny, (rect.width, rect.height))

    eye_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(eye_surf, (255, 255, 255), (0, 0, rect.width, rect.height))
    eye_surf.blit(gradient_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    surface.blit(eye_surf, rect.topleft)
    
    glint_x = rect.left + 35
    glint_y = rect.top + 40
    pygame.draw.circle(surface, HIGHLIGHT, (glint_x, glint_y), 22)
    pygame.draw.circle(surface, top, (glint_x + 10, glint_y + 10), 10)

    small_glint_x = glint_x - 5
    small_glint_y = glint_y + 45 
    pygame.draw.circle(surface, HIGHLIGHT, (small_glint_x, small_glint_y), 6)

def draw_eyelid(surface, rect, progress):
    """
    Fungsi menggambar kelopak mata untuk efek kedip
    """
    if progress <= 0:
        return 

    lid_height = rect.height * progress
    
    # Gambar kotak warna background menutupi mata
    cover_rect = pygame.Rect(rect.left - 5, rect.top - 5, rect.width + 10, lid_height + 5)
    pygame.draw.rect(surface, BG_COLOR, cover_rect)
    
    # Garis bulu mata
    line_y = rect.top + lid_height
    if line_y > rect.bottom: line_y = rect.bottom
        
    pygame.draw.line(surface, BLACK, (rect.left - 5, line_y), (rect.right + 5, line_y), 6)


# --- 4. Loop Utama ---
running = True
clock = pygame.time.Clock()

# --- VARIABEL TRANSISI KEDIP ---
blink_state = "closing" # Mulai dengan menutup
blink_progress = 0.0    
blink_speed = 0.05      # Kecepatan transisi

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill(BG_COLOR)
    
    # --- UPDATE LOGIKA KEDIP ---
    if blink_state == "closing":
        blink_progress += blink_speed
        if blink_progress >= 1.0:
            blink_progress = 1.0
            blink_state = "opening" # Ganti jadi membuka
            
    elif blink_state == "opening":
        blink_progress -= blink_speed
        if blink_progress <= 0.0:
            blink_progress = 0.0
            blink_state = "idle"    # Selesai, diam

    center_x = WIDTH // 2
    eye_y = 220
    eye_width = 110
    eye_height = 150
    dist_from_center = 140

    left_eye_rect = pygame.Rect(center_x - dist_from_center - eye_width, eye_y, eye_width, eye_height)
    right_eye_rect = pygame.Rect(center_x + dist_from_center, eye_y, eye_width, eye_height)

    # ==========================
    # BAGIAN 1: KABEL 
    # ==========================
    elbow_y = left_eye_rect.top - 50 
    points_kiri = [(-20, 60), (left_eye_rect.centerx, elbow_y), (left_eye_rect.centerx, left_eye_rect.top)]
    pygame.draw.lines(screen, BLACK, False, points_kiri, 4)

    points_kanan = [(WIDTH + 20, 60), (right_eye_rect.centerx, elbow_y), (right_eye_rect.centerx, right_eye_rect.top)]
    pygame.draw.lines(screen, BLACK, False, points_kanan, 4)

    points_tengah = [
        (left_eye_rect.right - 10, left_eye_rect.centery),
        (center_x, left_eye_rect.centery + 40),
        (right_eye_rect.left + 10, right_eye_rect.centery)
    ]
    pygame.draw.lines(screen, BLACK, False, points_tengah, 4)

    # ==========================
    # BAGIAN 2: MATA (HAPPY STYLE)
    # ==========================
    draw_eye_gradient(screen, left_eye_rect)
    draw_eye_gradient(screen, right_eye_rect)

    # ==========================================
    # BAGIAN BARU: KELOPAK MATA (KEDIP)
    # ==========================================
    # Digambar DI ATAS mata agar menutupi bola mata saat animasi
    draw_eyelid(screen, left_eye_rect, blink_progress)
    draw_eyelid(screen, right_eye_rect, blink_progress)

    # ==========================
    # BAGIAN 3: MULUT HAPPY (EXTRA ROUNDED BOTTOM)
    # ==========================
    # Konfigurasi bentuk mulut
    mouth_w = 240        # Lebar total mulut
    mouth_top_y = 400    # Posisi Y titik sudut atas
    curve_top_sag = 25   # Cekungan garis atas
    curve_bottom_depth = 130 # Kedalaman lengkungan bawah
    
    mouth_points = []
    steps = 60 # Jumlah titik diperbanyak agar lebih halus

    # 1. Generate Kurva ATAS
    for i in range(steps + 1):
        t = i / steps
        px = (center_x - mouth_w // 2) + (t * mouth_w)
        py = mouth_top_y + (curve_top_sag * 4 * t * (1 - t)) 
        mouth_points.append((px, py))

    # 2. Generate Kurva BAWAH (RUMUS ELIPS AGAR LEBIH BULAT)
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
    
    mouth_points.extend(reversed(bottom_points))

    # --- RENDERING MULUT ---
    # A. Gambar Dasar Mulut
    pygame.draw.polygon(screen, MOUTH_DARK, mouth_points)

    # B. Gambar Lidah (Masking)
    mouth_mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(mouth_mask, (255, 255, 255, 255), mouth_points)
    
    tongue_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    
    tongue_rect = pygame.Rect(center_x - mouth_w//2 + 10, mouth_top_y + 50, mouth_w - 20, 110)
    pygame.draw.ellipse(tongue_surf, TONGUE, tongue_rect)
    
    mouth_mask.blit(tongue_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    screen.blit(mouth_mask, (0, 0))

    # C. Outline Mulut
    pygame.draw.polygon(screen, BLACK, mouth_points, 8)
    pygame.draw.aalines(screen, BLACK, True, mouth_points)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()