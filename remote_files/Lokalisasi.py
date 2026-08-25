#!/usr/bin/env python3
"""
Lokalisasi_SAR.py  —  ROS 2 Jazzy  |  Logitech Brio 4K / C920  |  SAR (HEADLESS MODE)
=============================================================================
Arsitektur ditingkatkan ke ROS 2 murni (rclpy).
- Menggunakan kelas berbasis rclpy.node.Node.
- Eliminasi while loop (rospy.Rate) menjadi Timer Callback (Asinkron).
- Menggunakan tf2_ros.TransformBroadcaster untuk Transformasi.
- Sinkronisasi waktu menggunakan rclpy.time.Time (nanoseconds precision).
"""

import collections
import math
import argparse
import cv2
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.duration import Duration

from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseWithCovarianceStamped, Quaternion, PoseStamped, TransformStamped
from sensor_msgs.msg import Image, Imu, JointState, CompressedImage
from std_msgs.msg import Float32MultiArray, String, Float64, Bool
from cv_bridge import CvBridge, CvBridgeError
from tf2_ros import TransformBroadcaster

# Pastikan package kustom ini sudah di-build di workspace ROS 2 Anda
# from detection_msgs.msg import BoundingBoxes
from robotis_controller_msgs.msg import JointCtrlModule, StatusMsg
# from open_cr_module.msg import OrientationRPY
# from constants import warna


def euler_to_quaternion(roll, pitch, yaw):
    """Fungsi helper konversi euler ke quaternion tanpa dependensi tf1"""
    qx = np.sin(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) - np.cos(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
    qy = np.cos(roll/2) * np.sin(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.cos(pitch/2) * np.sin(yaw/2)
    qz = np.cos(roll/2) * np.cos(pitch/2) * np.sin(yaw/2) - np.sin(roll/2) * np.sin(pitch/2) * np.cos(yaw/2)
    qw = np.cos(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
    return [qx, qy, qz, qw]


# ══════════════════════════════════════════════════════════════════
# FEATURE DENSITY BRIDGE (SAR NOVELTY)
# ══════════════════════════════════════════════════════════════════
class FeatureDensityBridge:
    THRESHOLD      : float = 0.015
    SIGMA_NORMAL   : float = 0.15
    SIGMA_FALLBACK : float = 0.60
    HYSTERESIS_IN  : int   = 3
    HYSTERESIS_OUT : int   = 5

    def __init__(self, node_ref):
        self.node = node_ref  # Referensi node untuk logger ROS 2
        self.density         : float = 1.0
        self.is_fallback     : bool  = False
        self._streak_fb      : int   = 0
        self._streak_ok      : int   = 0

    def update(self, density: float):
        self.density = density
        if density < self.THRESHOLD:
            self._streak_fb += 1
            self._streak_ok  = 0
        else:
            self._streak_ok += 1
            self._streak_fb  = 0

        if not self.is_fallback and self._streak_fb >= self.HYSTERESIS_IN:
            self.is_fallback = True
            self.node.get_logger().warn(f"[FeatureDensityBridge] FALLBACK (Blind-Spot) Aktif! Density={density:.4f}")
        elif self.is_fallback and self._streak_ok >= self.HYSTERESIS_OUT:
            self.is_fallback = False
            self.node.get_logger().info("[FeatureDensityBridge] NORMAL Aktif (Fitur Ditemukan)")

    @property
    def sigma(self) -> float:
        return self.SIGMA_FALLBACK if self.is_fallback else self.SIGMA_NORMAL

    @property
    def noise_scale(self) -> float:
        return 2.0 if self.is_fallback else 1.0


# ══════════════════════════════════════════════════════════════════
# NODE LOKALISASI UTAMA (ROS 2)
# ══════════════════════════════════════════════════════════════════
class ImprovedOP3Localization(Node):
    def __init__(self, field_side='right', is_dead_reckoning=False):
        super().__init__('improved_op3_localization')
        
        self.is_dead_reckoning = is_dead_reckoning
        if self.is_dead_reckoning:
            self.get_logger().info("🔥 MODE DEAD RECKONING AKTIF: Vision bypass dinyalakan.")
        
        self.bridge = CvBridge()
        
        self.last_update_time = None
        self.previous_joint_states = None
        self.current_joint_states = None
        self.goal_joint_states = None
        self.pelvis_pose = None
        self.ball_position = None
        self.goal_position = None
        self.last_valid_ball_pos = None
        self.last_valid_goal_pos = None
        self.detected_landmarks = []
        self.is_walking_active = False
        
        self.yaw = 0.0
        self.last_yaw = 0
        self.yaw_offset = 0.0
        self.is_first_orientation = True

        self.ball_timeout = 1.0 # Dalam detik
        self.goal_timeout = 1.0
        self.last_ball_detection_time = None
        self.last_goal_detection_time = None
        
        self.coord_scale_factor = 1.0
        self.coord_offset_x = 0.0
        self.coord_offset_y = 0.0

        self.image_width = 320
        self.image_height = 240
        
        self.field_side = field_side
        self.field_length = 20.0  
        self.field_width = 20.0   
        self.center_circle_radius = 0.75
        self.field_orientation = None
        self.initial_heading = None
        self.initial_position = None
        self.is_orientation_confirmed = False
        self.motion_history = []
        self.max_history_size = 30
        
        # 1. ADAPTIVE KLD-SAMPLING CONFIG
        self.max_particles = 800
        self.min_particles = 100
        self.num_particles = self.min_particles
        self.initialization_attempts = 0
        self.max_initialization_attempts = 3
        self.is_position_confirmed = False
        self.min_detection_confidence = 0.7
        self.particles = self.init_particles()

        self.linear_acc_x = 0.0
        self.linear_acc_y = 0.0
        self.linear_acc_z = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.last_accel_time = self.get_clock().now()
        self.loopcount = 0
        self.linear_acc_x_sum = 0.0
        self.calib_count = 0
        self.filtered_acc_x = 0.0
        self.filtered_acc_y = 0.0
        self.alpha = 0.15
        self.linear_acc_y_sum = 0.0
        self.bias_acc_x = 0.0
        self.bias_acc_y = 0.0
        self.max_calib_samples = 100
        self.is_calibrated = False

        self.angular_vel_y = 0.0
        self.angular_vel_z = 0.0

        self.filtered_acc_x = 0.0
        self.filtered_acc_y = 0.0
        self.alpha = 0.15

        self.tf_broadcaster = TransformBroadcaster(self)
        self.map = OccupancyGrid()
        
        self.leg_joints = [
            'l_hip_yaw', 'l_hip_roll', 'l_hip_pitch', 'l_knee', 'l_ank_pitch', 'l_ank_roll',
            'r_hip_yaw', 'r_hip_roll', 'r_hip_pitch', 'r_knee', 'r_ank_pitch', 'r_ank_roll'
        ]
        self.joint_positions = {joint: 0.0 for joint in self.leg_joints}
        
        self.walking_params = {
            'x_offset': -0.02669158, 'y_offset': 0.025, 'z_offset': 0.037,
            'roll_offset': 0, 'pitch_offset': 0, 'yaw_offset': 0,
            'hip_pitch_offset': 7.000000052497138, 'period_time': 550,
            'dsp_ratio': 0.18, 'step_forward_back_ratio': 0.28,
            'foot_height': 0.06, 'swing_right_left': 0.028,
            'swing_top_down': 0.006, 'pelvis_offset': 0.4999999961268166,
            'arm_swing_gain': 0.2, 'balance_hip_roll_gain': 0.35,
            'balance_hip_pitch_gain': 1, 'balance_knee_gain': 0.3,
            'balance_ankle_roll_gain': 0.7, 'balance_ankle_pitch_gain': 0.9
        }
        
        self.STEP_LENGTH_SCALE = self.walking_params['step_forward_back_ratio'] * 0.1
        self.STEP_WIDTH_SCALE = self.walking_params['swing_right_left']
        self.TURN_SCALE = 0.1
        self.JOINT_MOVEMENT_THRESHOLD = 0.05
        self.YAW_MOVEMENT_THRESHOLD = self.walking_params['balance_hip_roll_gain'] * 0.1
        
        self.odometry_buffer = {
            'dx': collections.deque(maxlen=3),
            'dy': collections.deque(maxlen=3),
            'dtheta': collections.deque(maxlen=3)
        }
        
        self.leg_states = {
            'r_ank_pitch': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
            'r_ank_roll': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
            'r_knee': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
            'l_ank_pitch': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
            'l_ank_roll': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
            'l_knee': {'prev': 0.0, 'curr': 0.0, 'change': 0.0}
        }

        self.fd_bridge = FeatureDensityBridge(self)
        
        self.setup_ros_communications()
        self.init_visualization()
        self.init_map()

        # Timer Pengganti While Loop (Jalan di 30Hz)
        timer_period = 1.0 / 30.0
        self.timer = self.create_timer(timer_period, self.main_loop_callback)
        self.get_logger().info("Node OP3 Localization ROS 2 SAR Berhasil Dijalankan")

    def setup_ros_communications(self):
        # ── PUBLISHERS (ROS 2 Style) ──
        self.pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/op3/pose', 10)
        self.map_pub = self.create_publisher(OccupancyGrid, '/op3/map', 10)
        
        self.processed_img_pub = self.create_publisher(CompressedImage, '/sar/processed_image/compressed', 10)
        self.loc_map_pub       = self.create_publisher(Image, '/sar/localization_map', 10)
        self.density_pub       = self.create_publisher(Float64, '/sar/feature_density', 10)
        self.fallback_pub      = self.create_publisher(Bool, '/sar/fallback_status', 10)
        
        # ── SUBSCRIBERS (ROS 2 Style) ──
        self.image_sub = self.create_subscription(Image, '/image_raw', self.image_callback, 10)
        # self.orientation_sub = self.create_subscription(OrientationRPY, '/orientation/raw', self.orientation_callback, 10)
        self.joint_states_sub = self.create_subscription(JointState, '/robotis/present_joint_states', self.joint_states_callback, 10)
        self.goal_joint_states_sub = self.create_subscription(JointState, '/robotis/goal_joint_states', self.goal_joint_states_callback, 10)
        self.walking_command_sub = self.create_subscription(String, '/robotis/walking/command', self.walking_command_callback, 10)
        self.pelvis_pose_sub = self.create_subscription(PoseStamped, '/robotis/pelvis_pose', self.pelvis_pose_callback, 10)
        # self.yolo_detections_sub = self.create_subscription(BoundingBoxes, '/yolov5/detections', self.yolo_detections_callback, 10)
        self.coord_ball_sub = self.create_subscription(Quaternion, '/coord_ball', self.coord_ball_callback, 10)
        self.coord_goal_sub = self.create_subscription(Quaternion, '/coord_goal', self.coord_goal_callback, 10)
        self.imu_sub = self.create_subscription(Imu, '/robotis/open_cr/imu', self.imu_callback, 10)

    # ══════════════════════════════════════════════════════════════════
    # MAIN LOOP TIMER (Pengganti rcpy.Rate.sleep)
    # ══════════════════════════════════════════════════════════════════
    def main_loop_callback(self):
        self.determine_field_orientation()
        self.publish_pose()
        self.visualize()

    # ══════════════════════════════════════════════════════════════════
    # VISUAL PIPELINE UNTUK SAR
    # ══════════════════════════════════════════════════════════════════
    def image_callback(self, msg):
        if self.is_dead_reckoning:
            return  # Bypass vision processing entirely
            
        # --- 2. GAIT-SYNCHRONIZED VISION ---
        # Abaikan frame jika getaran kepala (Gyro Pitch/Yaw) sangat tinggi (> 1.0 rad/s)
        gyro_magnitude = math.sqrt(self.angular_vel_y**2 + self.angular_vel_z**2)
        if gyro_magnitude > 1.0:
            # Motion blur terdeteksi, lewati pemrosesan vision untuk menghemat CPU
            return

        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            self.process_image(cv_image)
        except CvBridgeError as e:
            self.get_logger().error(f"Failed to convert image: {e}")

    def process_image(self, image):
        resized = cv2.resize(image, (self.image_width, self.image_height))
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.2)
        edges = cv2.Canny(blurred, 50, 150)

        density = int(np.count_nonzero(edges)) / (self.image_width * self.image_height)
        self.fd_bridge.update(density)
        
        msg_density = Float64()
        msg_density.data = float(density)
        self.density_pub.publish(msg_density)
        
        msg_fallback = Bool()
        msg_fallback.data = bool(self.fd_bridge.is_fallback)
        self.fallback_pub.publish(msg_fallback)

        if self.fd_bridge.is_fallback:
            synthetic = self._make_synthetic_edges(self.image_height, self.image_width)
            edge_map = cv2.bitwise_or(edges, synthetic)
        else:
            edge_map = edges

        kernel = np.ones((3, 3), np.uint8)
        edge_map = cv2.morphologyEx(edge_map, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(edge_map, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        sar_features = self.analyze_sar_features(contours, edge_map.shape)

        self.update_particles_with_sar_features(sar_features)
        self.publish_visualize_processing(resized, gray, edges, edge_map)

    def _make_synthetic_edges(self, H, W):
        canvas = np.zeros((H, W), dtype=np.uint8)
        m = 5
        cv2.line(canvas, (0, m), (W-1, m), 255, 2)
        cv2.line(canvas, (0, H-m-1), (W-1, H-m-1), 255, 2)
        cv2.line(canvas, (m, 0), (m, H-1), 255, 2)
        cv2.line(canvas, (W-m-1, 0), (W-m-1, H-1), 255, 2)
        return canvas

    def analyze_sar_features(self, contours, image_shape):
        H, W = image_shape[:2]
        cx, cy = W // 2, H // 2
        MIN_AREA = 100
        valid = [c for c in contours if cv2.contourArea(c) > MIN_AREA]
        total_dist = 0.0
        total_pts = 0
        for cnt in valid:
            for pt in cnt:
                px, py = pt[0]
                total_dist += math.sqrt((px - cx)**2 + (py - cy)**2)
                total_pts += 1
        mean_dist = total_dist / max(total_pts, 1)
        return {'mean_distance': mean_dist}

    def update_particles_with_sar_features(self, features):
        if not self.particles: return
        sigma = self.fd_bridge.sigma
        z_obs = (features['mean_distance'] / max(self.image_width, self.image_height) 
                 * min(self.field_length, self.field_width) * 0.5)

        for i, (x, y, theta, _) in enumerate(self.particles):
            z_exp = math.sqrt(x**2 + y**2)
            diff = z_obs - z_exp
            w = math.exp(-(diff**2) / (2.0 * sigma**2))
            self.particles[i][3] = max(w, 1e-9)

        total_w = sum(p[3] for p in self.particles)
        if total_w > 0:
            for i in range(len(self.particles)):
                self.particles[i][3] /= total_w
        if total_w < 0.1:
            self.resample_particles()

    def publish_visualize_processing(self, original, gray, edges_raw, edge_map):
        try:
            H, W = original.shape[:2]
            vis = np.zeros((H*2, W*2, 3), dtype=np.uint8)

            vis[:H, :W] = original
            vis[:H, W:W*2] = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            vis[H:H*2, :W] = cv2.cvtColor(edges_raw, cv2.COLOR_GRAY2BGR)
            edge_bgr = cv2.cvtColor(edge_map, cv2.COLOR_GRAY2BGR)

            if self.fd_bridge.is_fallback:
                m = 8
                mask = np.zeros((H, W), dtype=np.uint8)
                mask[:m,:]=255; mask[H-m:,:]=255
                mask[:,:m]=255; mask[:,W-m:]=255
                synth_mask = cv2.bitwise_and(edge_map, mask)
                edge_bgr[synth_mask > 0] = (0, 0, 255)

            vis[H:H*2, W:W*2] = edge_bgr
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(vis, 'Original', (10, 18), font, 0.5, (255,255,255), 1)
            cv2.putText(vis, 'Grayscale', (W+10, 18), font, 0.5, (255,255,255), 1)
            cv2.putText(vis, 'Canny raw', (10, H+18), font, 0.5, (255,255,255), 1)
            status = "Edge+Synthetic" if self.fd_bridge.is_fallback else "Edge map"
            color = (0,0,255) if self.fd_bridge.is_fallback else (100,255,100)
            # ... (font and text drawing code) ...
            cv2.putText(vis, status, (W+10, H+18), font, 0.5, color, 1)

            msg = CompressedImage()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.format = "jpeg"
            # Kompres gambar ke format JPG sebelum dikirim
            _, compressed_data = cv2.imencode('.jpg', vis, [cv2.IMWRITE_JPEG_QUALITY, 80])
            msg.data = compressed_data.tobytes()
            self.processed_img_pub.publish(msg)
        except Exception as e:
            self.get_logger().warn(f"Processing visualization error: {e}")

    # ══════════════════════════════════════════════════════════════════
    # KINEMATIKA, ODOMETRY & IMU (ALVIN LOGIC IN ROS 2)
    # ══════════════════════════════════════════════════════════════════
    def meter_to_pixel(self, x, y, width, height):
        x_px = int((x + self.field_length/2) * width/self.field_length)
        y_px = int((y + self.field_width/2) * height/self.field_width)
        return x_px, y_px

    def pixel_to_meter(self, x_px, y_px, width, height):
        x = (x_px / width) * self.field_length - self.field_length/2
        y = (y_px / height) * self.field_width - self.field_width/2
        return x, y

    def init_particles(self):
        particles = []
        ref_pos = {'x': 0.0, 'y': 0.0, 'theta': 0.0} if self.field_side == 'right' else {'x': 0.0, 'y': 0.0, 'theta': math.pi}
        self.yaw_offset = -1 * ref_pos['theta']

        for _ in range(self.num_particles):
            noise_factor = 0.5 + self.initialization_attempts * 0.2
            x = np.random.normal(ref_pos['x'], 0.5 * noise_factor)
            y = np.random.normal(ref_pos['y'], 0.5 * noise_factor)
            theta = np.random.normal(ref_pos['theta'], 0.05)
            x = max(-self.field_length/2, min(x, self.field_length/2))
            y = max(-self.field_width/2, min(y, self.field_width/2))
            theta = math.atan2(math.sin(theta), math.cos(theta))
            particles.append([x, y, theta, 1.0/self.num_particles])
        return particles

    def imu_callback(self, msg):
        current_time = self.get_clock().now()
        dt = (current_time.nanoseconds - self.last_accel_time.nanoseconds) / 1e9
        self.last_accel_time = current_time

        # --- 1. PROSES KALIBRASI STATIS DAN LOW-PASS FILTER ---
        raw_acc_x = msg.linear_acceleration.x
        raw_acc_y = msg.linear_acceleration.y

        # Fase Kalibrasi: Kumpulkan 100 sampel data pertama saat robot diam murni
        if not self.is_calibrated:
            self.bias_acc_x += raw_acc_x
            self.bias_acc_y += raw_acc_y
            self.calib_count += 1
            
            if self.calib_count >= self.max_calib_samples:
                self.bias_acc_x /= self.max_calib_samples
                self.bias_acc_y /= self.max_calib_samples
                self.is_calibrated = True
                self.get_logger().info(f"[IMU] Kalibrasi Sukses! Bias X: {self.bias_acc_x:.4f}, Bias Y: {self.bias_acc_y:.4f}")
            return  # Jangan proses data sisa sebelum kalibrasi selesai mengunci angka offset

        # Jika fase kalibrasi selesai, kurangi nilai mentah dengan offset bias murni
        acc_x = raw_acc_x - self.bias_acc_x
        acc_y = raw_acc_y - self.bias_acc_y

        # Rumus Matematis Low-Pass Filter untuk memotong getaran tinggi
        self.filtered_acc_x = self.alpha * acc_x + (1.0 - self.alpha) * self.filtered_acc_x
        self.filtered_acc_y = self.alpha * acc_y + (1.0 - self.alpha) * self.filtered_acc_y

        # Masukkan hasil filter ke variabel pelacakan posisi dan partikel
        self.linear_acc_x = self.filtered_acc_x
        self.linear_acc_y = self.filtered_acc_y
        
        self.velocity_x += self.linear_acc_x * dt
        self.velocity_y += self.linear_acc_y * dt

        # --- 2. PROSES ORIENTASI (YAW) DARI QUATERNION IMU ---
        # Ekstrak Yaw murni dari IMU tanpa perlu open_cr_module
        q = msg.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        raw_yaw = math.atan2(siny_cosp, cosy_cosp)

        if self.is_first_orientation:
            self.yaw_offset += raw_yaw
            self.is_first_orientation = False

        self.last_yaw = self.yaw
        adjusted_yaw = raw_yaw - self.yaw_offset

        if self.field_side == 'right':
            adjusted_yaw = -adjusted_yaw

        self.yaw = math.atan2(math.sin(adjusted_yaw), math.cos(adjusted_yaw))
        self.update_particles_with_orientation(self.yaw)

        # --- 3. PROSES ANGULAR VELOCITY (GYRO) UNTUK MOTION BLUR ---
        self.angular_vel_y = msg.angular_velocity.y
        self.angular_vel_z = msg.angular_velocity.z

    def walking_command_callback(self, msg):
        prev_state = self.is_walking_active
        command = msg.data.lower()
        if command == "start":
            self.is_walking_active = True
            self.walking_start_time = self.get_clock().now()
        elif command == "stop":
            self.is_walking_active = False
            self.walking_start_time = None
        if prev_state != self.is_walking_active:
            self.get_logger().info(f"Walking state changed: {prev_state} -> {self.is_walking_active}")

    def init_map(self):
        resolution = 0.05
        width = int(self.field_length / resolution)
        height = int(self.field_width / resolution)
        self.map.header.frame_id = "map"
        self.map.info.resolution = resolution
        self.map.info.width = width
        self.map.info.height = height
        self.map.info.origin.position.x = -self.field_length / 2
        self.map.info.origin.position.y = -self.field_width / 2
        self.map.data = [0] * (width * height)
        self.map_image = np.zeros((height, width), dtype=np.uint8)
        self.map.data = self.map_image.flatten().tolist()
        self.map_pub.publish(self.map)

    def init_visualization(self):
        self.field_image = np.zeros((int(self.field_width * 100), 
                                   int(self.field_length * 100), 3), 
                                   dtype=np.uint8)

    def detect_walking_phase(self, leg_prefix):
        try:
            if self.current_joint_states is None: return 'unknown'
            joints = {}
            for joint in [f'{leg_prefix}_knee', f'{leg_prefix}_ank_pitch', 
                         f'{leg_prefix}_hip_pitch', f'{leg_prefix}_hip_roll']:
                try:
                    idx = self.current_joint_states.name.index(joint)
                    joints[joint] = self.current_joint_states.position[idx]
                except ValueError:
                    return 'unknown'

            knee_val = abs(joints[f'{leg_prefix}_knee'])
            ank_val = abs(joints[f'{leg_prefix}_ank_pitch'])
            hip_pitch_val = abs(joints[f'{leg_prefix}_hip_pitch'])

            if knee_val < 0.2 and ank_val < 0.15: return 'stance'
            elif knee_val > 0.3 or hip_pitch_val > 0.25: return 'swing'
            else: return 'transition'
        except Exception: return 'unknown'
    
    def is_walking(self):
        try:
            right_phase = self.detect_walking_phase('r')
            left_phase = self.detect_walking_phase('l')
            right_velocities, left_velocities = [], []
            
            if self.current_joint_states:
                for i, name in enumerate(self.current_joint_states.name):
                    if name.startswith('r_'):
                        right_velocities.append(abs(self.current_joint_states.velocity[i]))
                    elif name.startswith('l_'):
                        left_velocities.append(abs(self.current_joint_states.velocity[i]))
            
            avg_right_vel = sum(right_velocities) / len(right_velocities) if right_velocities else 0
            avg_left_vel = sum(left_velocities) / len(left_velocities) if left_velocities else 0
            
            is_phases_alternating = ((right_phase == 'stance' and left_phase == 'swing') or
                                     (right_phase == 'swing' and left_phase == 'stance'))
            
            velocity_threshold = 0.1
            is_significant_movement = (avg_right_vel > velocity_threshold or avg_left_vel > velocity_threshold)
            is_both_legs_active = (right_phase != 'unknown' and left_phase != 'unknown' and
                                   not (right_phase == 'transition' and left_phase == 'transition'))
            
            return is_phases_alternating and is_significant_movement and is_both_legs_active
        except Exception: return False
    
    def calculate_odometry(self):
        try:
            if self.previous_joint_states is None or self.current_joint_states is None:
                return 0.0, 0.0, 0.0

            # Menggunakan API Waktu ROS 2 murni
            t_curr = Time.from_msg(self.current_joint_states.header.stamp)
            t_prev = Time.from_msg(self.previous_joint_states.header.stamp)
            dt = (t_curr.nanoseconds - t_prev.nanoseconds) / 1e9

            if dt <= 0: return 0.0, 0.0, 0.0

            joint_indices = {}
            for joint in ['r_hip_pitch', 'l_hip_pitch', 'r_knee', 'l_knee',
                         'r_ank_pitch', 'l_ank_pitch', 'r_hip_roll', 'l_hip_roll']:
                try: joint_indices[joint] = self.current_joint_states.name.index(joint)
                except ValueError: return 0.0, 0.0, 0.0

            current_positions = {joint: self.current_joint_states.position[idx] for joint, idx in joint_indices.items()}
            previous_positions = {joint: self.previous_joint_states.position[idx] for joint, idx in joint_indices.items()}
            joint_changes = {joint: abs(current_positions[joint] - previous_positions[joint]) for joint in joint_indices.keys()}

            KNEE_THRESHOLD = 0.003
            ANKLE_THRESHOLD = 0.010
            HIP_ROLL_THRESHOLD = 0.01

            right_moving = (joint_changes['r_knee'] > KNEE_THRESHOLD or joint_changes['r_ank_pitch'] > ANKLE_THRESHOLD)
            left_moving = (joint_changes['l_knee'] > KNEE_THRESHOLD or joint_changes['l_ank_pitch'] > ANKLE_THRESHOLD)

            dx = dy = dtheta = 0.0

            if right_moving or left_moving:
                # KALIBRASI 16 Juli 2026 (Revisi 2): step_size di-fine-tune ke 0.017
                # Uji Pretes6 menunjukkan step_size 0.01 menghasilkan 1.19m (underestimate).
                # (2.0 / 1.19) * 0.01 = ~0.017 agar akurasi 1:1 di rumput sintetis.
                step_size = 0.017
                knee_movement = max(joint_changes['r_knee'], joint_changes['l_knee'])
                ankle_movement = max(joint_changes['r_ank_pitch'], joint_changes['l_ank_pitch'])
                movement_scale = (knee_movement + ankle_movement) / (KNEE_THRESHOLD + ANKLE_THRESHOLD)
                dx = step_size * movement_scale

            hip_roll_diff = (joint_changes['r_hip_roll'] - joint_changes['l_hip_roll'])
            if abs(hip_roll_diff) > HIP_ROLL_THRESHOLD:
                dy = 0.02 * np.sign(hip_roll_diff)

            hip_pitch_diff = (joint_changes['r_hip_pitch'] - joint_changes['l_hip_pitch'])
            if abs(hip_pitch_diff) > HIP_ROLL_THRESHOLD:
                dtheta = 0.1 * np.sign(hip_pitch_diff)

            time_scale = min(dt * 2.0, 1.0)
            dx *= time_scale
            dy *= time_scale
            dtheta *= time_scale

            if hasattr(self, 'walking_params'):
                dx *= self.walking_params['step_forward_back_ratio']
                dy *= self.walking_params['swing_right_left']

            if not hasattr(self, 'odometry_buffer'):
                self.odometry_buffer = {'dx': collections.deque(maxlen=3), 'dy': collections.deque(maxlen=3), 'dtheta': collections.deque(maxlen=3)}

            self.odometry_buffer['dx'].append(dx)
            self.odometry_buffer['dy'].append(dy)
            self.odometry_buffer['dtheta'].append(dtheta)

            dx = sum(self.odometry_buffer['dx']) / len(self.odometry_buffer['dx'])
            dy = sum(self.odometry_buffer['dy']) / len(self.odometry_buffer['dy'])
            dtheta = sum(self.odometry_buffer['dtheta']) / len(self.odometry_buffer['dtheta'])
            return dx, dy, dtheta
        except Exception: return 0.0, 0.0, 0.0

    def update_particles_with_accelerometer(self):
        if not hasattr(self, 'particles') or not self.particles: return
        if not hasattr(self, 'delta_position'): return

        robot_pose = self.estimate_pose()
        theta = robot_pose[2]
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        
        global_acc_x = -0.2 * cos_theta - self.linear_acc_y * sin_theta
        global_acc_y = -0.2 * sin_theta + self.linear_acc_y * cos_theta

        if self.field_side == 'right':
            global_acc_x = -global_acc_x
            global_acc_y = -global_acc_y

        dt = 0.1
        self.velocity_x += global_acc_x * dt
        self.velocity_y += global_acc_y * dt

        delta_x = self.velocity_x * dt + 0.5 * global_acc_x * dt**2
        delta_y = self.velocity_y * dt + 0.5 * global_acc_y * dt**2

        ns = self.fd_bridge.noise_scale
        for i in range(len(self.particles)):
            x, y, theta, weight = self.particles[i]
            noise_x = np.random.normal(0, 0.01 * ns)
            noise_y = np.random.normal(0, 0.01 * ns)
            
            new_x = x + delta_x + noise_x
            new_y = y + delta_y + noise_y
            new_x = max(min(new_x, self.field_length/2), -self.field_length/2)
            new_y = max(min(new_y, self.field_width/2), -self.field_width/2)
            self.particles[i] = [new_x, new_y, theta, weight]

        if not self.is_walking():
            self.velocity_x = 0.0
            self.velocity_y = 0.0
        self.delta_position = (0.0, 0.0)

    def update_particles_with_orientation(self, yaw):
        if not hasattr(self, 'particles'): return
        ns = self.fd_bridge.noise_scale
        for i in range(len(self.particles)):
            x, y, _, weight = self.particles[i]
            yaw_noise = np.random.normal(0, 0.01 * ns)
            adjusted_yaw = yaw + yaw_noise
            if hasattr(self, 'field_orientation') and self.field_orientation == 'inverted':
                adjusted_yaw = math.pi - adjusted_yaw

            while adjusted_yaw > math.pi: adjusted_yaw -= 2 * math.pi
            while adjusted_yaw < -math.pi: adjusted_yaw += 2 * math.pi
            self.particles[i] = [x, y, adjusted_yaw, weight]

    def update_particles_with_odometry(self):
        if not hasattr(self, 'particles') or not self.particles: return
        dx, dy, dtheta = self.calculate_odometry()
        if dx == 0 and dy == 0 and dtheta == 0: return

        ns = self.fd_bridge.noise_scale
        for i in range(len(self.particles)):
            x, y, theta, weight = self.particles[i]
            dx_noise = np.random.normal(0, abs(dx) * 0.1 * ns)
            dy_noise = np.random.normal(0, abs(dy) * 0.1 * ns)
            dtheta_noise = np.random.normal(0, abs(dtheta) * 0.1 * ns)

            cos_theta = math.cos(theta)
            sin_theta = math.sin(theta)

            if self.field_side == 'right':
                global_dx = (dx + dx_noise) * cos_theta - (dy + dy_noise) * sin_theta
                global_dy = (dx + dx_noise) * sin_theta + (dy + dy_noise) * cos_theta
            else:
                global_dx = -((dx + dx_noise) * cos_theta - (dy + dy_noise) * sin_theta)
                global_dy = -((dx + dx_noise) * sin_theta + (dy + dy_noise) * cos_theta)

            new_x = x + global_dx
            new_y = y + global_dy
            new_theta = theta + (dtheta + dtheta_noise)
            new_theta = math.atan2(math.sin(new_theta), math.cos(new_theta))

            new_x = max(min(new_x, self.field_length/2), -self.field_length/2)
            new_y = max(min(new_y, self.field_width/2), -self.field_width/2)

            movement_confidence = self.calculate_motion_confidence(dx, dy)
            new_weight = weight * movement_confidence
            self.particles[i] = [new_x, new_y, new_theta, new_weight]

        total_weight = sum(p[3] for p in self.particles)
        if total_weight > 0:
            for i in range(len(self.particles)): self.particles[i][3] /= total_weight
        if total_weight < 0.1:
            self.resample_particles()

    def calculate_motion_confidence(self, dx, dy):
        if not hasattr(self, 'motion_history') or len(self.motion_history) < 2: return 1.0
        recent_dx = sum(m['dx'] for m in self.motion_history[-5:]) / 5 if len(self.motion_history) >= 5 else dx
        recent_dy = sum(m['dy'] for m in self.motion_history[-5:]) / 5 if len(self.motion_history) >= 5 else dy
        dx_deviation = abs(dx - recent_dx) / (abs(recent_dx) + 1e-6)
        dy_deviation = abs(dy - recent_dy) / (abs(recent_dy) + 1e-6)
        confidence = 1.0 / (1.0 + dx_deviation + dy_deviation)
        return max(0.5, min(1.0, confidence))

    def resample_particles(self):
        # --- ADAPTIVE KLD-SAMPLING ---
        target_particles = self.max_particles if self.fd_bridge.is_fallback else self.min_particles
            
        N = len(self.particles)
        weights = [p[3] for p in self.particles]
        total = sum(weights)
        if total <= 0:
            self.num_particles = target_particles
            self.particles = self.init_particles()
            return
            
        weights = [w/total for w in weights]
        cumsum = np.cumsum(weights)
        
        # Resample menyesuaikan target_particles (Dinamis)
        step = 1.0/target_particles
        start = np.random.uniform(0, step)
        indices = []
        j = 0
        for k in range(target_particles):
            target = start + k*step
            while j < N-1 and cumsum[j] < target: j += 1
            indices.append(j)
            
        self.num_particles = target_particles
        self.particles = [[*self.particles[idx][:3], 1.0/target_particles] for idx in indices]

    def estimate_pose(self):
        if len(self.particles) == 0: return (0, 0, 0)
        total_weight = sum(p[3] for p in self.particles)
        if total_weight == 0:
            x = np.mean([p[0] for p in self.particles])
            y = np.mean([p[1] for p in self.particles])
        else:
            x = sum(p[0] * p[3] for p in self.particles) / total_weight
            y = sum(p[1] * p[3] for p in self.particles) / total_weight
        return (x, y, self.yaw)

    def publish_pose(self):
        pose = self.estimate_pose()
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.pose.position.x = pose[0]
        msg.pose.pose.position.y = pose[1]
        msg.pose.pose.position.z = 0.0
        
        q = euler_to_quaternion(0, 0, pose[2])
        msg.pose.pose.orientation.x = q[0]
        msg.pose.pose.orientation.y = q[1]
        msg.pose.pose.orientation.z = q[2]
        msg.pose.pose.orientation.w = q[3]
        
        covariance = [0.0] * 36
        
        # --- 3. DYNAMIC COVARIANCE (FUSI SENSOR DINAMIS) ---
        # Covariance membesar secara melengkung/eksponensial jika fitur menurun
        if self.fd_bridge.density > 0.0:
            dynamic_cov = 0.005 / (self.fd_bridge.density + 0.001)
        else:
            dynamic_cov = 1.0
            
        cov_pos = min(max(dynamic_cov, 0.05), 1.0) # Clamp di rentang 0.05 - 1.0
        
        covariance[0] = cov_pos
        covariance[7] = cov_pos
        covariance[14] = cov_pos
        covariance[21] = 0.1
        covariance[28] = 0.1
        covariance[35] = cov_pos * 0.5
        msg.pose.covariance = covariance
        
        self.pose_pub.publish(msg)

        # TF2 Broadcaster di ROS 2 (TransformStamped)
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'map'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = pose[0]
        t.transform.translation.y = pose[1]
        t.transform.translation.z = 0.0
        t.transform.rotation.x = q[0]
        t.transform.rotation.y = q[1]
        t.transform.rotation.z = q[2]
        t.transform.rotation.w = q[3]
        self.tf_broadcaster.sendTransform(t)

    def determine_field_orientation(self):
        if not self.is_orientation_confirmed:
            current_pose = self.estimate_pose()
            if self.initial_position is None:
                self.initial_position = current_pose
                self.initial_heading = self.yaw
            
            if self.field_side == 'right':
                if abs(self.yaw) < math.pi/2: self.field_orientation = 'normal'
                else: self.field_orientation = 'inverted'
            else:
                if abs(self.yaw) > math.pi/2: self.field_orientation = 'normal'
                else: self.field_orientation = 'inverted'
            self.is_orientation_confirmed = True

    # Callbacks yang tidak terpakai utamanya di SAR, tapi dijaga agar tidak error
    def joint_states_callback(self, msg):
        if self.last_update_time is None:
            self.last_update_time = self.get_clock().now()
            self.previous_joint_states = msg
            return
        self.current_joint_states = msg
        self.update_particles_with_odometry()
        self.previous_joint_states = self.current_joint_states
        self.last_update_time = self.get_clock().now()

    def goal_joint_states_callback(self, msg): self.goal_joint_states = msg
    def pelvis_pose_callback(self, msg): self.pelvis_pose = msg
    #  def yolo_detections_callback(self, msg): self.detected_landmarks = msg.bounding_boxes
    def coord_ball_callback(self, msg): pass
    def coord_goal_callback(self, msg): pass

    # ══════════════════════════════════════════════════════════════════
    # VISUALISASI MAP HEADLESS (Publish ke Topik)
    # ══════════════════════════════════════════════════════════════════
    def visualize(self):
        self.field_image.fill(0)
        height, width = self.field_image.shape[:2]

        top_left = self.meter_to_pixel(-self.field_length/2, -self.field_width/2, width, height)
        bottom_right = self.meter_to_pixel(self.field_length/2, self.field_width/2, width, height)
        cv2.rectangle(self.field_image, top_left, bottom_right, (255, 255, 255), 2)

        cv2.line(self.field_image, (int(width/2), 0), (int(width/2), int(height)), (255, 255, 255), 2)
        center_x, center_y = int(width/2), int(height/2)
        cv2.line(self.field_image, (0, center_y), (width, center_y), (0, 0, 255), 1)
        cv2.line(self.field_image, (center_x, 0), (center_x, height), (255, 0, 0), 1)

        for p in self.particles:
            x, y = self.meter_to_pixel(p[0], p[1], width, height)
            if 0 <= x < width and 0 <= y < height:
                cv2.circle(self.field_image, (x, y), 1, (0, 255, 0), -1)

        pose = self.estimate_pose()
        robot_x, robot_y = self.meter_to_pixel(pose[0], pose[1], width, height)

        if 0 <= robot_x < width and 0 <= robot_y < height:
            cv2.circle(self.field_image, (robot_x, robot_y), 5, (0, 0, 255), -1)
            arrow_length = 20
            arrow_x = robot_x + int(arrow_length * math.cos(-pose[2]))
            arrow_y = robot_y - int(arrow_length * math.sin(-pose[2]))
            cv2.arrowedLine(self.field_image, (robot_x, robot_y), (arrow_x, arrow_y), (0, 0, 255), 2)

        self.add_visualization_text(pose)
        # [MODIFIKASI HEADLESS]: Publish peta ke ROS
        try:
            resized_map = cv2.resize(self.field_image, (600, 600))
            map_msg = self.bridge.cv2_to_imgmsg(resized_map, "bgr8")
            self.loc_map_pub.publish(map_msg)
        except CvBridgeError:
            pass
    def add_visualization_text(self, pose):
        font, font_scale, thickness, font_color = cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2, (255, 255, 255)
        
        # Perhatikan koordinat Y (angka kedua) sekarang menjadi 40, 80, 120, 160
        cv2.putText(self.field_image, f"Pose: ({pose[0]:.2f}, {pose[1]:.2f})", (10, 40), font, font_scale, font_color, thickness)
        cv2.putText(self.field_image, f"Orientation: {math.degrees(pose[2]):.1f} deg", (10, 80), font, font_scale, font_color, thickness)

        mode_label = "FALLBACK (SYNTHETIC)" if self.fd_bridge.is_fallback else "NORMAL"
        mode_color = (0, 140, 255) if self.fd_bridge.is_fallback else (100, 255, 100)
        cv2.putText(self.field_image, f"Vision: {mode_label}", (10, 120), font, font_scale, mode_color, thickness)
        cv2.putText(self.field_image, f"IMU Acc X: {self.linear_acc_x:.3f} Y: {self.linear_acc_y:.3f}", (10, 160), font, font_scale, (0, 255, 0), thickness)
        

# ══════════════════════════════════════════════════════════════════
# ENTRY POINT ROS 2
# ══════════════════════════════════════════════════════════════════
def main(args=None):
    # Inisialisasi rclpy sebelum parsing agar argumen bawaan ROS 2 diabaikan dengan aman
    rclpy.init(args=args)
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--side', type=str, default='right', choices=['right', 'left'])
    parser.add_argument('--dead-reckoning', action='store_true', help='Bypass kamera dan hanya gunakan IMU+Kinematika')
    # parse_known_args mengabaikan argumen tambahan yang disisipkan oleh ROS 2 launch system
    parsed_args, _ = parser.parse_known_args()
    
    node = ImprovedOP3Localization(field_side=parsed_args.side, is_dead_reckoning=parsed_args.dead_reckoning)
    
    try:
        # Menjaga node tetap hidup (Timer Callback berjalan asinkron di sini)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Bersihkan node saat dimatikan (Ctrl+C)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
