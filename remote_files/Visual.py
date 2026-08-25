#!/usr/bin/env python3
"""
Visual_SAR.py  —  ROS 2 Jazzy  |  Base Station GUI
=============================================================================
Bertindak sebagai "Thin Client". Skrip ini murni hanya membaca (subscribe) 
topik ROS 2 dari Lokalisasi_SAR.py dan merendernya menggunakan Pygame.

ARSITEKTUR ROS 2:
- Menggunakan rclpy.node.Node.
- Menjalankan rclpy.spin() di BACKGROUND THREAD agar tidak memblokir 
  main-loop dari GUI Pygame (Mencegah freeze/lag pada antarmuka).
- DILARANG memproses gambar menggunakan operasi Canny/Matriks di sini.
"""

import math
import threading
import numpy as np
import cv2
import pygame
import os
os.environ['SDL_VIDEODRIVER'] = 'x11'     # Paksa gunakan server layar standar Linux
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide" # Sembunyikan pesan hello pygame
import rclpy
from rclpy.node import Node
from cv_bridge import CvBridge, CvBridgeError

from geometry_msgs.msg import PoseWithCovarianceStamped
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Float64, Bool

class VisualizerSAR(Node):
    def __init__(self):
        super().__init__('visualizer_sar_node')
        self.bridge = CvBridge()
        
        # ── Setup Pygame GUI ──
        pygame.init()
        # Lebar 1100px (600px untuk Peta, 500px untuk HUD & Kamera)
        self.width, self.height = 1300, 800
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("SAR Humanoid Localization Monitor (Base Station - ROS 2)")
        self.clock = pygame.time.Clock()
        
        # Font Setup
        self.font_title = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_info = pygame.font.SysFont("Arial", 18)
        self.font_alert = pygame.font.SysFont("Arial", 20, bold=True)
        
        # ── State Variables ──
        self.robot_pose = [0.0, 0.0, 0.0]
        self.feature_density = 0.0
        self.fallback_active = False
        
        self.map_surface = None      # Permukaan untuk Peta 2D
        self.camera_surface = None   # Permukaan untuk Kamera 4-Panel
        
        # ── ROS 2 Subscribers ──
        self.create_subscription(PoseWithCovarianceStamped, '/op3/pose', self.pose_callback, 10)
        self.create_subscription(CompressedImage, '/sar/processed_image/compressed', self.camera_callback, 10)
        self.create_subscription(Image, '/sar/localization_map', self.map_callback, 10)
        self.create_subscription(Float64, '/sar/feature_density', self.density_callback, 10)
        self.create_subscription(Bool, '/sar/fallback_status', self.fallback_callback, 10)
        
        self.get_logger().info("Menunggu aliran data dari Intel NUC melalui jaringan DDS...")

    # ══════════════════════════════════════════════════════════════════
    # CALLBACKS SENSOR DAN GAMBAR
    # ══════════════════════════════════════════════════════════════════
    def pose_callback(self, msg):
        self.robot_pose[0] = msg.pose.pose.position.x
        self.robot_pose[1] = msg.pose.pose.position.y
        # Ekstrak Yaw dari Quaternion (Manual tanpa library tambahan TF)
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.robot_pose[2] = math.atan2(siny_cosp, cosy_cosp)

    def density_callback(self, msg):
        self.feature_density = msg.data

    def fallback_callback(self, msg):
        self.fallback_active = msg.data

    def camera_callback(self, msg):
        """Menerima frame 4-panel Canny/Poligon dari NUC."""
        try:
            # Decode the compressed image
            np_arr = np.frombuffer(msg.data, np.uint8)
            cv_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            # Ensure decode was successful
            if cv_img is None:
                return

            # Convert BGR (OpenCV) to RGB (Pygame)
            rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            # Scale image
            rgb_img = cv2.resize(rgb_img, (640, 480))
            # Rotate for Pygame
            surf = pygame.surfarray.make_surface(np.rot90(rgb_img))
            self.camera_surface = pygame.transform.flip(surf, True, False)
        except Exception as e: # Catch broader exceptions just in case
            self.get_logger().error(f"Camera Callback Error: {e}")
        
        pygame.event.pump()

    def map_callback(self, msg):
        """Menerima Peta 2D (beserta partikel & lintasan) dari NUC."""
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            surf = pygame.surfarray.make_surface(np.rot90(rgb_img))
            self.map_surface = pygame.transform.flip(surf, True, False)
        except CvBridgeError as e:
            self.get_logger().error(f"Map Callback Error: {e}")

    # ══════════════════════════════════════════════════════════════════
    # RENDERING GUI PYGAME (Berjalan di Main Thread)
    # ══════════════════════════════════════════════════════════════════
    def draw_gui(self):
        # Background Dasar
        self.screen.fill((20, 20, 20))

        # 1. RENDER PETA 2D (Panel Kiri)
        if self.map_surface:
            self.screen.blit(self.map_surface, (0, 0))
            pygame.draw.rect(self.screen, (100, 100, 100), (0, 0, 600, 600), 2)
        else:
            txt = self.font_info.render("Menunggu data peta dari NUC...", True, (150, 150, 150))
            self.screen.blit(txt, (180, 280))

        # 2. RENDER PANEL HUD (Panel Kanan)
        panel_x = 620
        
        # Judul HUD
        title = self.font_title.render("TELEMETRI SAR (Intel NUC)", True, (255, 255, 255))
        self.screen.blit(title, (panel_x, 20))
        pygame.draw.line(self.screen, (100, 100, 100), (panel_x, 50), (1080, 50), 2)

        # Render Kamera Canny 4-Panel
        if self.camera_surface:
            self.screen.blit(self.camera_surface, (panel_x, 70))
            pygame.draw.rect(self.screen, (255, 255, 255), (panel_x, 70, 640, 480), 2)
        else:
            pygame.draw.rect(self.screen, (40, 40, 40), (panel_x, 70, 640, 480))
            txt = self.font_info.render("NO VIDEO SIGNAL", True, (100, 100, 100))
            self.screen.blit(txt, (panel_x + 250, 300))

        # Indikator Status & Data Spasial
        data_y = 570
        
        # Data Pose
        pose_txt = f"Estimasi Pose  :  X: {self.robot_pose[0]:.2f}m   |   Y: {self.robot_pose[1]:.2f}m"
        yaw_txt  = f"Heading (Yaw)  :  {math.degrees(self.robot_pose[2]):.1f}°"
        self.screen.blit(self.font_info.render(pose_txt, True, (200, 255, 200)), (panel_x, data_y))
        self.screen.blit(self.font_info.render(yaw_txt, True, (200, 255, 200)), (panel_x, data_y + 25))
        
        # Data Kepadatan Fitur (Density)
        density_txt = f"Visual Density   :  {self.feature_density * 100:.2f} %"
        self.screen.blit(self.font_info.render(density_txt, True, (255, 255, 200)), (panel_x, data_y + 60))

        # Kotak Status Peringatan (Fallback Indicator)
        status_box_rect = pygame.Rect(panel_x, data_y + 100, 640, 50)
        if self.fallback_active:
            pygame.draw.rect(self.screen, (200, 40, 40), status_box_rect)  # Merah Peringatan
            status_txt = "⚠️ BLIND-SPOT: SYNTHETIC POLYGON ACTIVE"
            txt_color = (255, 255, 255)
        else:
            pygame.draw.rect(self.screen, (40, 150, 40), status_box_rect)  # Hijau Aman
            status_txt = "✅ NORMAL: REAL EDGE TRACKING"
            txt_color = (255, 255, 255)
            
        pygame.draw.rect(self.screen, (255, 255, 255), status_box_rect, 2)
        txt_surf = self.font_alert.render(status_txt, True, txt_color)
        
        txt_rect = txt_surf.get_rect(center=status_box_rect.center)
        self.screen.blit(txt_surf, txt_rect)

    def run_pygame_loop(self):
        """Fungsi yang menjalankan GUI Pygame secara sinkron di Main Thread."""
        rate_limit = 30
        running = True
        try:
            while running and rclpy.ok():
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False

                self.draw_gui()
                
                pygame.display.flip()
                self.clock.tick(rate_limit)
                
        except Exception as e:
            self.get_logger().error(f"Pygame GUI Error: {e}")
        finally:
            pygame.quit()


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT & THREADING ROS 2
# ══════════════════════════════════════════════════════════════════
def main(args=None):
    rclpy.init(args=args)
    vis_node = VisualizerSAR()

    # Pisahkan eksekusi ROS 2 ke thread belakang (Background Thread)
    # Agar data terus masuk (spin) tanpa memblokir perputaran UI Pygame
    ros_thread = threading.Thread(target=rclpy.spin, args=(vis_node,), daemon=True)
    ros_thread.start()

    # Jalankan Pygame di Main Thread
    vis_node.run_pygame_loop()

    # Pembersihan sistem saat jendela GUI ditutup
    vis_node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    ros_thread.join()

if __name__ == '__main__':
    main()
