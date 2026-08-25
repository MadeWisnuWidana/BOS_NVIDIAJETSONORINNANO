#!/usr/bin/env python3
import collections
import rclpy
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped
from rclpy.time import Time
from rclpy.duration import Duration

from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseWithCovarianceStamped, Quaternion, PoseStamped
from sensor_msgs.msg import Image, Imu, JointState
from std_msgs.msg import Float32MultiArray,String
from cv_bridge import CvBridge, CvBridgeError
import cv2
import numpy as np
from detection_msgs.msg import BoundingBoxes  # Changed from vision_msgs
from robotis_controller_msgs.msg import JointCtrlModule
import math
from robotis_controller_msgs.msg import StatusMsg
from open_cr_module.msg import OrientationRPY

class OrientationMsg:
    def __init__(self):
        self.header = Header()
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0

class ImprovedOP3Localization(Node):
    def __init__(self,field_side='right'):
        super().__init__('improved_op3_localization_alvin')
        
        # Initialize visualization windows first
        self.image_processing_window = 'Image Processing Results'
        # cv2.namedWindow(self.image_processing_window)
        self.visualization_window_name = 'Localization Visualization'
        # cv2.namedWindow(self.visualization_window_name)
        
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
        self.is_walking_active=False
        # Initialize orientation values
        self.yaw = 0.0
        self.last_yaw = 0
        self.yaw_offset = 0.0
        self.is_first_orientation = True

        self.ball_timeout = Duration(seconds=1.0)  # 1 second timeout
        self.goal_timeout = Duration(seconds=1.0)
        self.last_ball_detection_time = None
        self.last_goal_detection_time = None
        
        # Add conversion factors
        self.coord_scale_factor = 1.0
        self.coord_offset_x = 0.0
        self.coord_offset_y = 0.0

        self.image_width = 320
        self.image_height = 240
        
        self.field_side = field_side
        self.field_length = 9.0
        self.field_width = 6.0
        self.field_orientation = None  # 'normal' or 'inverted'
        self.initial_heading = None
        self.initial_position = None
        self.is_orientation_confirmed = False
        self.motion_history = []
        self.max_history_size = 30
        self.num_particles = 50
        self.initialization_attempts = 0
        self.max_initialization_attempts = 3
        self.is_position_confirmed = False
        self.min_detection_confidence = 0.7
        self.particles = self.init_particles()
        
        self.tf_listener = tf.TransformListener()
        self.tf_broadcaster = TransformBroadcaster(self)
        
        self.map = OccupancyGrid()
        self.leg_joints = [
            'l_hip_yaw', 'l_hip_roll', 'l_hip_pitch', 'l_knee', 'l_ank_pitch', 'l_ank_roll',
            'r_hip_yaw', 'r_hip_roll', 'r_hip_pitch', 'r_knee', 'r_ank_pitch', 'r_ank_roll'
        ]
        self.joint_positions = {joint: 0.0 for joint in self.leg_joints}
        
        self.walking_params = {
            'x_offset': -0.02669158,
            'y_offset': 0.025,
            'z_offset': 0.037,
            'roll_offset': 0,
            'pitch_offset': 0,
            'yaw_offset': 0,
            'hip_pitch_offset': 7.000000052497138,
            'period_time': 550,  # dalam millisecond
            'dsp_ratio': 0.18,
            'step_forward_back_ratio': 0.28,
            'foot_height': 0.06,
            'swing_right_left': 0.028,
            'swing_top_down': 0.006,
            'pelvis_offset': 0.4999999961268166,
            'arm_swing_gain': 0.2,
            'balance_hip_roll_gain': 0.35,
            'balance_hip_pitch_gain': 1,
            'balance_knee_gain': 0.3,
            'balance_ankle_roll_gain': 0.7,
            'balance_ankle_pitch_gain': 0.9
        }
        
        # Inisialisasi parameter odometri berdasarkan walking params
        self.STEP_LENGTH_SCALE = self.walking_params['step_forward_back_ratio'] * 0.1  # Konversi ke meter
        self.STEP_WIDTH_SCALE = self.walking_params['swing_right_left']
        self.TURN_SCALE = 0.1  # Tetap menggunakan 0.1 sebagai baseline untuk rotasi
        
        # Threshold berdasarkan parameter balance
        self.JOINT_MOVEMENT_THRESHOLD = 0.05  # Disesuaikan dengan balance gain
        self.YAW_MOVEMENT_THRESHOLD = self.walking_params['balance_hip_roll_gain'] * 0.1
        
        # Buffer untuk smoothing
        self.odometry_buffer = {
            'dx': collections.deque(maxlen=3),
            'dy': collections.deque(maxlen=3),
            'dtheta': collections.deque(maxlen=3)
        }
        self.landmark_positions = {
            'center_circle': (0, 0),
            'penalty_mark_1': (3.0, 0),   # Right penalty mark
            'penalty_mark_2': (-3.0, 0),  # Left penalty mark
        }
        self.leg_states = {
        'r_ank_pitch': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
        'r_ank_roll': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
        'r_knee': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
        'l_ank_pitch': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
        'l_ank_roll': {'prev': 0.0, 'curr': 0.0, 'change': 0.0},
        'l_knee': {'prev': 0.0, 'curr': 0.0, 'change': 0.0}
        }

        # Threshold berdasarkan parameter robot
        self.joint_thresholds = {
            'ankle_pitch': self.walking_params['balance_ankle_pitch_gain'] * 0.01,
            'ankle_roll': self.walking_params['balance_ankle_roll_gain'] * 0.01,
            'knee': self.walking_params['balance_knee_gain'] * 0.01,
            'min_change': 0.001
        }
        self.setup_ros_communications()
        self.init_map()
        self.init_visualization()


    def setup_ros_communications(self):
        # Publishers
        self.pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/op3/pose', 10)
        self.map_pub = self.create_publisher(OccupancyGrid, '/op3/map', 1)
        
        # Subscribers
        self.image_sub = self.create_subscription(Image, '/image_raw', self.image_callback, 10)
        self.orientation_sub = self.create_subscription(OrientationRPY, '/orientation/raw', self.orientation_callback, 10)
        self.joint_states_sub = self.create_subscription(JointState, '/robotis/present_joint_states', self.joint_states_callback, 10)
        self.goal_joint_states_sub = self.create_subscription(JointState, '/robotis/goal_joint_states', self.goal_joint_states_callback, 10)
        self.walking_command_sub = self.create_subscription(String, '/robotis/walking/command', self.walking_command_callback, 10)
        self.pelvis_pose_sub = self.create_subscription(PoseStamped, '/robotis/pelvis_pose', self.pelvis_pose_callback, 10)
        self.yolo_detections_sub = self.create_subscription(BoundingBoxes, '/yolov5/detections', self.yolo_detections_callback, 10)
        self.coord_ball_sub = self.create_subscription(Quaternion, '/coord_ball', self.coord_ball_callback, 10)
        self.coord_goal_sub = self.create_subscription(Quaternion, '/coord_goal', self.coord_goal_callback, 10)

    def init_particles(self):
        particles = []
        initial_positions = {
            'right': {
                'pinggir': {'x': 4.0, 'y': 2.0, 'theta': 0.0},  # FIXED: Changed from math.pi to 0.0
                'penalty': {'x': 3.5, 'y': 0.0, 'theta': 0.0}, # FIXED: Changed from math.pi to 0.0
                'goalie': {'x': 4.5, 'y': 0.0, 'theta': 0.0}   # FIXED: Changed from math.pi to 0.0
            },
            'left': {
                'pinggir': {'x': -4.0, 'y': -2.0, 'theta': math.pi},  # FIXED: Changed from 0.0 to math.pi
                'penalty': {'x': -3.5, 'y': 0.0, 'theta': math.pi}, # FIXED: Changed from 0.0 to math.pi
                'goalie': {'x': -4.5, 'y': 0.0, 'theta': math.pi}   # FIXED: Changed from 0.0 to math.pi
            }
        }

        # Use penalty position as default for more accurate initial position
        ref_pos = initial_positions[self.field_side]['pinggir']

        # Generate particles with more focused distribution
        for _ in range(self.num_particles):
            noise_factor = 0.5 + self.initialization_attempts * 0.2

            x = np.random.normal(ref_pos['x'], 0.2 * noise_factor)
            y = np.random.normal(ref_pos['y'], 0.2 * noise_factor)
            theta = np.random.normal(ref_pos['theta'], 0.05)

            # Field boundary constraints
            if self.field_side == 'right':
                x = max(3.5, min(x, self.field_length/2))
            else:
                x = max(-self.field_length/2, min(x, -3.5))

            y = max(-self.field_width/2, min(y, self.field_width/2))
            theta = math.atan2(math.sin(theta), math.cos(theta))

            particles.append([x, y, theta, 1.0/self.num_particles])

        return particles
    
    def verify_position(self):
        """Verify if the current position estimate matches the expected field side"""
        pose = self.estimate_pose()
        current_x = pose[0]
        
        # Check if the estimated position matches the initialized side
        if self.field_side == 'right' and current_x < 0:
            return False
        elif self.field_side == 'left' and current_x > 0:
            return False
        
        return True
    
    def walking_command_callback(self, msg):
        prev_state = self.is_walking_active
        command = msg.data.lower()

        if command == "start":
            self.is_walking_active = True
            self.walking_start_time = self.get_clock().now().to_msg()
        elif command == "stop":
            self.is_walking_active = False
            self.walking_start_time = None

        if prev_state != self.is_walking_active:
            self.get_logger().info(f"Walking state changed: {prev_state} -> {self.is_walking_active}")

    def verify_initial_position(self):
        """Verifikasi posisi awal robot lebih detail"""
        current_pose = self.estimate_pose()
        x, y, theta = current_pose

        # 1. Verifikasi sisi lapangan dan jarak dari garis penalti
        penalty_line = 4.0  # Jarak garis penalti dari tengah lapangan
        if self.field_side == 'right':
            if x < penalty_line:  # Robot harus berada di belakang garis penalti
                return False
        else:
            if x > -penalty_line:  # Robot harus berada di belakang garis penalti
                return False

        # 2. Verifikasi orientasi awal
        expected_theta = math.pi if self.field_side == 'right' else 0.0
        if abs(math.atan2(math.sin(theta - expected_theta), 
                          math.cos(theta - expected_theta))) > math.pi/6:  # Toleransi dikurangi ke pi/6
            return False

        # 3. Verifikasi jarak dari posisi referensi
        ref_pos = {
            'right': {'x': 4.0, 'y': 0.0},  # Diubah ke posisi di belakang garis penalti
            'left': {'x': -4.0, 'y': 0.0}
        }[self.field_side]

        dist_to_ref = math.sqrt((x - ref_pos['x'])**2 + (y - ref_pos['y'])**2)
        if dist_to_ref > 0.5:  # Toleransi dikurangi dari 1.0 ke 0.5 meter
            return False

        return True
    
    def reinitialize_if_needed(self):
        """Check and reinitialize particles if position seems incorrect"""
        """Reinisialisasi dengan pengecekan lebih detail"""
        if not self.is_position_confirmed:
            if not self.verify_initial_position():
                self.initialization_attempts += 1
                if self.initialization_attempts < self.max_initialization_attempts:
                    self.get_logger().warn(f"Position verification failed, reinitializing particles " +
                                f"(attempt {self.initialization_attempts})")
                    if self.initialization_attempts == 1:
                        # Coba dengan distribusi yang lebih sempit
                        self.num_particles = int(self.num_particles * 1.5)
                    elif self.initialization_attempts == 2:
                        # Coba dengan distribusi yang lebih luas
                        self.num_particles = int(self.num_particles * 0.75)
                    self.particles = self.init_particles()
                else:
                    self.get_logger().warn("Max initialization attempts reached, using best estimate")
                    self.is_position_confirmed = True
            else:
                self.get_logger().info("Initial position verified successfully")
                self.is_position_confirmed = True
                # Catat posisi awal yang berhasil untuk referensi
                self.initial_verified_pose = self.estimate_pose()

    def init_map(self):
        resolution = 0.05  # 5cm per pixel
        width = int(self.field_length / resolution)
        height = int(self.field_width / resolution)
        
        self.map.header.frame_id = "map"
        self.map.info.resolution = resolution
        self.map.info.width = width
        self.map.info.height = height
        self.map.info.origin.position.x = -self.field_length / 2
        self.map.info.origin.position.y = -self.field_width / 2
        
        # Initialize empty map
        self.map.data = [0] * (width * height)
        self.map_image = np.zeros((height, width), dtype=np.uint8)
        
        # Draw field features
        self.draw_field_lines()
        
        # Publish initial map
        self.map.data = self.map_image.flatten().tolist()
        self.map_pub.publish(self.map)

    def draw_field_lines(self):
        # Field border
        self.draw_line(-4.5, -3.0, 4.5, -3.0)  # Bottom line
        self.draw_line(-4.5, 3.0, 4.5, 3.0)    # Top line
        self.draw_line(-4.5, -3.0, -4.5, 3.0)  # Left line
        self.draw_line(4.5, -3.0, 4.5, 3.0)    # Right line
        
        # Center line
        self.draw_line(0, -3.0, 0, 3.0)
        
        # Center circle
        self.draw_circle(0, 0, 0.75)

    def draw_line(self, x1, y1, x2, y2):
        x1_px = int((x1 + self.field_length / 2) / self.map.info.resolution)
        y1_px = int((y1 + self.field_width / 2) / self.map.info.resolution)
        x2_px = int((x2 + self.field_length / 2) / self.map.info.resolution)
        y2_px = int((y2 + self.field_width / 2) / self.map.info.resolution)
        cv2.line(self.map_image, (x1_px, y1_px), (x2_px, y2_px), 100, 1)

    def draw_circle(self, x, y, radius):
        x_px = int((x + self.field_length / 2) / self.map.info.resolution)
        y_px = int((y + self.field_width / 2) / self.map.info.resolution)
        radius_px = int(radius / self.map.info.resolution)
        cv2.circle(self.map_image, (x_px, y_px), radius_px, 100, 1)

    def init_visualization(self):
        self.field_image = np.zeros((int(self.field_width * 100), 
                                   int(self.field_length * 100), 3), 
                                   dtype=np.uint8)

    def orientation_callback(self, msg):
        # Get yaw from orientation/raw topic
        if self.is_first_orientation:
            self.yaw_offset = msg.yaw
            self.is_first_orientation = False

        # Convert to radians and normalize
        self.last_yaw = self.yaw
        raw_yaw = math.radians(msg.yaw - self.yaw_offset)

        # Adjust yaw based on field side - FIXED: Reversed the logic
        if self.field_side == 'right':
            raw_yaw = -raw_yaw  # Inverse for right side instead of left

        # Normalize angle to [-pi, pi]
        self.yaw = math.atan2(math.sin(raw_yaw), math.cos(raw_yaw))

        # Update particles orientation
        self.update_particles_with_orientation(self.yaw)

    def update_leg_states(self):
        if self.current_joint_states is None or self.previous_joint_states is None:
            return False
        # Update nilai untuk setiap joint kaki
        for joint_name in self.leg_states.keys():
            try:
                curr_idx = self.current_joint_states.name.index(joint_name)
                prev_idx = self.previous_joint_states.name.index(joint_name)
                # Update nilai current dan previous
                self.leg_states[joint_name]['curr'] = self.current_joint_states.position[curr_idx]
                self.leg_states[joint_name]['prev'] = self.previous_joint_states.position[prev_idx]
                # Hitung perubahan
                self.leg_states[joint_name]['change'] = abs(
                    self.leg_states[joint_name]['curr'] - 
                    self.leg_states[joint_name]['prev']
                )
                self.get_logger().debug(f"{joint_name} change: {self.leg_states[joint_name]['change']:.6f}")
            except ValueError as e:
                self.get_logger().warn(f"Joint {joint_name} not found: {e}")
                return False
        return True
        
    def detect_walking_pattern(self):
        """
        Deteksi pola walking dari pergerakan kaki (ankle dan knee)
        """
        try:
            is_moving, movement_details = self.analyze_leg_movement()
            if not is_moving:
                return False

            # Cek pola alternating antara kaki kanan dan kiri
            right_total = movement_details['right']['total_change']
            left_total = movement_details['left']['total_change']

            # Cek knee movement untuk konfirmasi walking
            right_knee_moving = movement_details['right']['knee']['change'] > self.joint_thresholds['knee']
            left_knee_moving = movement_details['left']['knee']['change'] > self.joint_thresholds['knee']

            # Rasio pergerakan antara kaki
            if min(right_total, left_total) > 0:
                movement_ratio = max(right_total, left_total) / min(right_total, left_total)
            else:
                movement_ratio = float('inf')

            # Walking biasanya memiliki:
            # 1. Rasio pergerakan yang seimbang antara kaki kanan dan kiri
            # 2. Pergerakan knee yang alternating
            # 3. Koordinasi antara ankle dan knee
            BALANCE_RATIO_THRESHOLD = 2.0
            is_balanced = movement_ratio < BALANCE_RATIO_THRESHOLD
            has_knee_movement = right_knee_moving or left_knee_moving

            if is_balanced and has_knee_movement:
                self.get_logger().info("Walking pattern detected:")
                self.get_logger().info(f"  Right/Left ratio: {movement_ratio:.2f}")
                self.get_logger().info(f"  Right total: {right_total:.6f}")
                self.get_logger().info(f"  Left total: {left_total:.6f}")
                self.get_logger().info(f"  Knee movement - Right: {right_knee_moving}, Left: {left_knee_moving}")
                return True

            return False

        except Exception as e:
            self.get_logger().error(f"Error detecting walking pattern: {e}")
            return False 
        
    def analyze_leg_movement(self):
        """
        Analisis detail pergerakan kaki (ankle dan knee)
        Return: (is_moving, movement_details)
        """
        try:
            if not self.update_leg_states():
                return False, {}

            movement_details = {
                'right': {
                    'ankle': {
                        'pitch_change': self.leg_states['r_ank_pitch']['change'],
                        'roll_change': self.leg_states['r_ank_roll']['change']
                    },
                    'knee': {
                        'change': self.leg_states['r_knee']['change']
                    },
                    'total_change': 0.0,
                    'is_moving': False
                },
                'left': {
                    'ankle': {
                        'pitch_change': self.leg_states['l_ank_pitch']['change'],
                        'roll_change': self.leg_states['l_ank_roll']['change']
                    },
                    'knee': {
                        'change': self.leg_states['l_knee']['change']
                    },
                    'total_change': 0.0,
                    'is_moving': False
                }
            }

            # Analisis pergerakan kaki kanan
            right_ankle_total = (movement_details['right']['ankle']['pitch_change'] + 
                               movement_details['right']['ankle']['roll_change'])
            right_knee = movement_details['right']['knee']['change']

            movement_details['right']['total_change'] = right_ankle_total + right_knee
            movement_details['right']['is_moving'] = (
                movement_details['right']['ankle']['pitch_change'] > self.joint_thresholds['ankle_pitch'] or
                movement_details['right']['ankle']['roll_change'] > self.joint_thresholds['ankle_roll'] or
                movement_details['right']['knee']['change'] > self.joint_thresholds['knee']
            )

            # Analisis pergerakan kaki kiri
            left_ankle_total = (movement_details['left']['ankle']['pitch_change'] + 
                              movement_details['left']['ankle']['roll_change'])
            left_knee = movement_details['left']['knee']['change']

            movement_details['left']['total_change'] = left_ankle_total + left_knee
            movement_details['left']['is_moving'] = (
                movement_details['left']['ankle']['pitch_change'] > self.joint_thresholds['ankle_pitch'] or
                movement_details['left']['ankle']['roll_change'] > self.joint_thresholds['ankle_roll'] or
                movement_details['left']['knee']['change'] > self.joint_thresholds['knee']
            )

            # Hitung total pergerakan
            total_movement = (movement_details['right']['total_change'] + 
                            movement_details['left']['total_change'])

            # Log detail pergerakan jika signifikan
            if total_movement > self.joint_thresholds['min_change']:
                self.get_logger().info("Leg Movement Analysis:")
                self.get_logger().info("Right Leg:")
                self.get_logger().info(f"  Ankle pitch change: {movement_details['right']['ankle']['pitch_change']:.6f}")
                self.get_logger().info(f"  Ankle roll change: {movement_details['right']['ankle']['roll_change']:.6f}")
                self.get_logger().info(f"  Knee change: {movement_details['right']['knee']['change']:.6f}")
                self.get_logger().info("Left Leg:")
                self.get_logger().info(f"  Ankle pitch change: {movement_details['left']['ankle']['pitch_change']:.6f}")
                self.get_logger().info(f"  Ankle roll change: {movement_details['left']['ankle']['roll_change']:.6f}")
                self.get_logger().info(f"  Knee change: {movement_details['left']['knee']['change']:.6f}")
                self.get_logger().info(f"Total movement: {total_movement:.6f}")

            # Deteksi pergerakan signifikan
            is_moving = (movement_details['right']['is_moving'] or 
                        movement_details['left']['is_moving'])

            return is_moving, movement_details

        except Exception as e:
            self.get_logger().error(f"Error analyzing leg movement: {e}")
            return False, {}
        except Exception as e:
            self.get_logger().error(f"Error updating leg states: {e}")
            return False


    def update_particles_with_orientation(self, yaw):
        if not hasattr(self, 'particles'):
            return

        for i in range(len(self.particles)):
            x, y, _, weight = self.particles[i]

            # Add small noise to yaw
            yaw_noise = np.random.normal(0, 0.01)

            # Adjust orientation based on field orientation - FIXED: Modified orientation logic
            adjusted_yaw = yaw + yaw_noise
            if hasattr(self, 'field_orientation') and self.field_orientation == 'inverted':
                adjusted_yaw = math.pi - adjusted_yaw  # FIXED: Changed from += math.pi to = math.pi - adjusted_yaw

            # Normalize angle
            while adjusted_yaw > math.pi:
                adjusted_yaw -= 2 * math.pi
            while adjusted_yaw < -math.pi:
                adjusted_yaw += 2 * math.pi

            self.particles[i] = [x, y, adjusted_yaw, weight]


    def joint_states_callback(self, msg):
        if self.last_update_time is None:
            self.last_update_time = self.get_clock().now().to_msg()
            self.previous_joint_states = msg
            return

        self.current_joint_states = msg
        self.update_particles_with_odometry()
        self.previous_joint_states = self.current_joint_states
        self.last_update_time = self.get_clock().now().to_msg()

    def image_callback(self, msg):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            self.process_image(cv_image)
        except CvBridgeError as e:
            self.get_logger().error(f"Failed to convert image: {e}")

    def goal_joint_states_callback(self, msg):
        self.goal_joint_states = msg

    def pelvis_pose_callback(self, msg):
        self.pelvis_pose = msg

    def yolo_detections_callback(self, msg):
        self.detected_landmarks = msg.bounding_boxes

    def coord_ball_callback(self, msg):

        if msg.x == -1.0 and msg.y == -1.0 and msg.z == -1.0 and msg.w == -1.0:
            self.ball_position = None
            return
        
    # Get bounding box center coordinates (normalized in [0,1])
        bbox_center_x = msg.x
        bbox_center_y = msg.y
        distance = msg.z
    
    # Convert image coordinates to field coordinates
    # Normalize to [-1,1] and flip y-axis since image coordinates are top-down
        normalized_x = (bbox_center_x - 0.5) * 2.0
        normalized_y = -1 * (bbox_center_y - 0.5) * 2.0  # Flip y-axis
    
    # Calculate ball position relative to robot using distance and normalized coordinates
    # x is forward distance, y is lateral distance (right positive)
        rel_x = distance * math.cos(math.atan2(normalized_y, normalized_x))
        rel_y = distance * math.sin(math.atan2(normalized_y, normalized_x))
    
    # Get current robot pose
        robot_pose = self.estimate_pose()
                
        robot_angle=robot_pose[2]
        # Transform to global field coordinates using robot's position and orientation
        global_x = robot_pose[0] + (rel_x * math.cos(robot_angle) - rel_y * math.sin(robot_angle))
        global_y = robot_pose[1] + (rel_x * math.sin(robot_angle) + rel_y * math.cos(robot_angle))
        
        # Apply field boundaries
        global_x = max(min(global_x, self.field_length/2), -self.field_length/2)
        global_y = max(min(global_y, self.field_width/2), -self.field_width/2)
        
        # Update ball position with global coordinates and distance
        self.ball_position = (global_x, global_y, distance)
        self.last_ball_detection_time = self.get_clock().now().to_msg()
    
    
    
    def transform_coordinates(self, x, y):
        """Transform coordinates from vision system to field coordinates"""
        # Convert from vision coordinates to field coordinates
        field_x = x * self.field_length/2
        field_y = y * self.field_width/2
        
        return field_x, field_y
    
    def update_motion_history(self, dx, dy):
        """Update motion history with new movement"""
        self.motion_history.append({
            'dx': dx,
            'dy': dy,
            'timestamp': self.get_clock().now().to_msg()
        })
        
        # Maintain history size
        while len(self.motion_history) > self.max_history_size:
            self.motion_history.pop(0)

    def determine_field_orientation(self):
        """Menentukan orientasi lapangan berdasarkan posisi robot dan landmark"""
        if not self.is_orientation_confirmed:
            current_pose = self.estimate_pose()
            
            # 1. Initialize with first position
            if self.initial_position is None:
                self.initial_position = current_pose
                self.initial_heading = self.yaw
            
            # 2. Check for nearest landmark
            nearest_landmark = self.find_nearest_landmark()
            if nearest_landmark:
                orientation = self.determine_orientation_from_landmark(nearest_landmark)
                if orientation:
                    self.field_orientation = orientation
                    self.is_orientation_confirmed = True
                    return
            
            # 3. Use initial heading and field side
            if self.field_side == 'right':
                if abs(self.yaw) < math.pi/2:  # Roughly facing forward
                    self.field_orientation = 'normal'
                else:
                    self.field_orientation = 'inverted'
            else:  # left side
                if abs(self.yaw) > math.pi/2:  # Roughly facing forward
                    self.field_orientation = 'normal'
                else:
                    self.field_orientation = 'inverted'
            
            self.is_orientation_confirmed = True
    
    def find_nearest_landmark(self):
        """Mencari landmark terdekat dari posisi robot"""
        if not hasattr(self, 'detected_landmarks') or not self.detected_landmarks:
            return None
            
        current_pose = self.estimate_pose()
        nearest = None
        min_dist = float('inf')
        
        for landmark in self.detected_landmarks:
            if hasattr(landmark, 'Class') and landmark.Class in ['penalty_mark', 'center_circle']:
                if hasattr(landmark, 'x') and hasattr(landmark, 'y'):
                    dist = math.sqrt((current_pose[0] - landmark.x)**2 + 
                                   (current_pose[1] - landmark.y)**2)
                    if dist < min_dist:
                        min_dist = dist
                        nearest = landmark
                    
        return nearest
    
    def determine_orientation_from_landmark(self, landmark):
        """Menentukan orientasi berdasarkan landmark terdekat"""
        if not landmark:
            return None
            
        current_pose = self.estimate_pose()
        
        if not hasattr(landmark, 'Class') or not hasattr(landmark, 'x'):
            return None
            
        if landmark.Class == 'penalty_mark':
            if self.field_side == 'right':
                return 'normal' if landmark.x > current_pose[0] else 'inverted'
            else:
                return 'normal' if landmark.x < current_pose[0] else 'inverted'
                
        return None

    def coord_goal_callback(self, msg):
        current_time = self.get_clock().now().to_msg()
        
        # Check if goal is not detected (all values are -1)
        if msg.x == -1.0 and msg.y == -1.0 and msg.z == -1.0 and msg.w == -1.0:
            if (self.last_goal_detection_time is None or 
                (current_time.nanoseconds - self.last_goal_detection_time.nanoseconds) / 1e9 > 1.0):
                self.goal_position = None
                self.get_logger().debug("Goal not detected")
                return
        else:
            # Convert quaternion coordinates to position
            x = msg.x
            y = msg.y
            
            # Apply coordinate transformation
            transformed_x = x * self.coord_scale_factor + self.coord_offset_x
            transformed_y = y * self.coord_scale_factor + self.coord_offset_y
            
            # Store position
            self.goal_position = (transformed_x, transformed_y)
            self.last_valid_goal_pos = self.goal_position
            self.last_goal_detection_time = current_time
            
            self.get_logger().debug(f"Goal detected at: {self.goal_position}")

    def process_image(self, image):
        """
        Enhanced image processing with improved penalty box detection and distance estimation
        """
        # Resize for consistency in processing
        resized_image = cv2.resize(image, (320, 240))
        hsv = cv2.cvtColor(resized_image, cv2.COLOR_BGR2HSV)

        # Enhanced field detection with better range
        lower_green = np.array([35, 50, 50])
        upper_green = np.array([85, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)

        # Enhanced line detection with better threshold
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        mask_white = cv2.inRange(hsv, lower_white, upper_white)

        # Morphological operations to clean noise
        kernel = np.ones((3,3), np.uint8)
        mask_white = cv2.morphologyEx(mask_white, cv2.MORPH_OPEN, kernel)
        mask_white = cv2.morphologyEx(mask_white, cv2.MORPH_CLOSE, kernel)

        # Combine masks with appropriate weights
        combined_mask = cv2.addWeighted(mask_green, 0.3, mask_white, 0.7, 0)

        # Detect edges for analysis
        edges = cv2.Canny(combined_mask, 50, 150)

        # Find contours with hierarchy for better structure analysis
        contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # Analyze and classify field features
        field_features = self.analyze_field_features(contours, hierarchy, resized_image.shape)

        # Update particle weights based on detected features
        self.update_particles_with_field_features(field_features)

        # Visualize processing steps
        self.visualize_processing(resized_image, mask_green, mask_white, combined_mask)
        
    def visualize_processing(self, original, mask_green, mask_white, combined_mask):
        """
        Create visualization of image processing steps
        """
        try:
            # Create visualization image
            vis_image = np.zeros((original.shape[0]*2, original.shape[1]*2, 3), dtype=np.uint8)

            # Original image
            vis_image[:original.shape[0], :original.shape[1]] = original

            # Green mask
            green_vis = cv2.cvtColor(mask_green, cv2.COLOR_GRAY2BGR)
            vis_image[:original.shape[0], original.shape[1]:original.shape[1]*2] = green_vis

            # White mask
            white_vis = cv2.cvtColor(mask_white, cv2.COLOR_GRAY2BGR)
            vis_image[original.shape[0]:original.shape[0]*2, :original.shape[1]] = white_vis

            # Combined mask
            combined_vis = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
            vis_image[original.shape[0]:original.shape[0]*2, original.shape[1]:original.shape[1]*2] = combined_vis

            # Add labels
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(vis_image, 'Original', (10, 20), font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(vis_image, 'Green Mask', (original.shape[1]+10, 20), font, 0.5, (255, 255, 255), 1)
            cv2.putText(vis_image, 'White Mask', (10, original.shape[0]+20), font, 0.5, (255, 255, 255), 1)
            cv2.putText(vis_image, 'Combined', (original.shape[1]+10, original.shape[0]+20), font, 0.5, (255, 255, 255), 1)

            # cv2.imshow(self.image_processing_window, vis_image)
            # cv2.waitKey(1)
        except Exception as e:
            self.get_logger().warn(f"Visualization error: {e}")

    def update_particles_with_field_features(self, features):
        """
        Update particle weights based on detected field features
        """
        if not self.particles:
            return

        for i in range(len(self.particles)):
            x, y, theta, w = self.particles[i]
            weight = 1.0

            # Update based on penalty box
            if features['penalty_box']:
                penalty_dist = self.distance_to_penalty_box(x, y, features['penalty_box'])
                weight *= math.exp(-penalty_dist * 0.5)

            # Update based on center circle
            if features['center_circle']:
                circle_dist = self.distance_to_center_circle(x, y, features['center_circle'])
                weight *= math.exp(-circle_dist * 0.3)

            # Update based on field lines
            for line in features['field_lines']:
                line_dist = self.distance_to_field_line(x, y, line)
                weight *= math.exp(-line_dist * 0.2)

            # Update particle weight
            self.particles[i][3] = weight

        # Normalize weights
        total_weight = sum(p[3] for p in self.particles)
        if total_weight > 0:
            for i in range(len(self.particles)):
                self.particles[i][3] /= total_weight


    def distance_to_penalty_box(self, x, y, penalty_box):
        """
        Calculate distance from particle to nearest point on penalty box
        """
        corners = penalty_box['corners']
        min_dist = float('inf')

        # Convert corners to field coordinates and calculate minimum distance
        for i in range(len(corners)):
            p1 = corners[i][0]
            p2 = corners[(i+1) % len(corners)][0]

            # Calculate distance to line segment
            dist = self.point_to_line_segment_distance(x, y, p1, p2)
            min_dist = min(min_dist, dist)

        return min_dist

    def get_line_endpoints(self, contour):
        """
        Get endpoints of a line contour
        """
        # Find the two points that are furthest apart
        max_distance = 0
        endpoints = None

        for i in range(len(contour)):
            for j in range(i + 1, len(contour)):
                p1 = contour[i][0]
                p2 = contour[j][0]
                dist = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

                if dist > max_distance:
                    max_distance = dist
                    endpoints = (p1, p2)

        return endpoints

    def analyze_field_features(self, contours, hierarchy, image_shape):
        """
        Analisis komprehensif fitur lapangan termasuk kotak penalti
        """
        features = {
            'penalty_box': None,
            'field_lines': [],
            'center_circle': None,
            'penalty_mark': None
        }

        height, width = image_shape[:2]

        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area < 100:  # Skip contours yang terlalu kecil
                continue

            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = float(w)/h if h != 0 else 0
            extent = float(area)/(w*h) if w*h != 0 else 0

            # Deteksi kotak penalti
            if len(approx) >= 4 and len(approx) <= 6:
                if 1.2 < aspect_ratio < 2.5 and area > 1000:  # Adjusted ratios
                    # Verifikasi tambahan untuk kotak penalti
                    if self.verify_penalty_box(approx, width, height):
                        features['penalty_box'] = {
                            'corners': approx,
                            'center': (x + w//2, y + h//2),
                            'dimensions': (w, h)
                        }

            # Deteksi lingkaran tengah
            elif 0.8 < extent < 1.2 and 0.8 < aspect_ratio < 1.2:
                (cx, cy), radius = cv2.minEnclosingCircle(contour)
                if 20 < radius < 50:
                    features['center_circle'] = (int(cx), int(cy), int(radius))

            # Deteksi garis
            elif len(approx) <= 4 and aspect_ratio > 3:
                if len(contour) >= 5:
                    (cx, cy), (MA, ma), angle = cv2.fitEllipse(contour)
                    if ma > 4 * MA:
                        features['field_lines'].append({
                            'center': (int(cx), int(cy)),
                            'length': ma,
                            'angle': angle,
                            'endpoints': self.get_line_endpoints(contour)
                        })

        return features

    def verify_penalty_box(self, approx, image_width, image_height):
        """
        Verifikasi kotak penalti dengan metode yang lebih akurat
        """
        # Convert to field coordinates with better perspective consideration
        field_points = []
        for point in approx:
            px, py = point[0]
            # Tambahkan kompensasi perspektif
            depth_factor = 1.0 + (py / image_height) * 0.5  # Objek lebih jauh tampak lebih kecil

            field_x = ((px - image_width/2) / depth_factor) * self.field_length/image_width
            field_y = ((py - image_height/2) / depth_factor) * self.field_width/image_height
            field_points.append((field_x, field_y))

        # Verifikasi dimensi dengan toleransi relatif
        box_width = max(p[0] for p in field_points) - min(p[0] for p in field_points)
        box_height = max(p[1] for p in field_points) - min(p[1] for p in field_points)

        # Expected dimensions with relative tolerance
        EXPECTED_WIDTH = 2.0  # meter
        EXPECTED_HEIGHT = 4.0  # meter
        RELATIVE_TOLERANCE = 0.2  # 20% tolerance

        # Calculate relative errors
        width_error = abs(box_width - EXPECTED_WIDTH) / EXPECTED_WIDTH
        height_error = abs(box_height - EXPECTED_HEIGHT) / EXPECTED_HEIGHT

        # Verify aspect ratio
        actual_ratio = box_width / box_height if box_height != 0 else 0
        expected_ratio = EXPECTED_WIDTH / EXPECTED_HEIGHT
        ratio_error = abs(actual_ratio - expected_ratio) / expected_ratio

        # Additional geometric checks
        is_rectangular = self.verify_rectangle_shape(approx)
        is_properly_oriented = self.verify_box_orientation(field_points)

        return (width_error < RELATIVE_TOLERANCE and 
                height_error < RELATIVE_TOLERANCE and 
                ratio_error < RELATIVE_TOLERANCE and
                is_rectangular and 
                is_properly_oriented)

    def verify_rectangle_shape(self, approx):
        """
        Verifikasi bahwa bentuk benar-benar rectangular
        """
        # Harus memiliki 4 sudut
        if len(approx) != 4:
            return False

        # Hitung sudut antar sisi
        angles = []
        for i in range(4):
            p1 = approx[i][0]
            p2 = approx[(i+1)%4][0]
            p3 = approx[(i+2)%4][0]

            # Hitung sudut menggunakan dot product
            v1 = p2 - p1
            v2 = p3 - p2
            angle = abs(np.degrees(
                np.arccos(
                    np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                )
            ))
            angles.append(angle)

        # Semua sudut harus mendekati 90 derajat
        return all(abs(angle - 90) < 15 for angle in angles)

    def verify_box_orientation(self, field_points):
        """
        Verifikasi orientasi kotak penalti sesuai dengan sisi lapangan
        """
        # Tentukan orientasi berdasarkan sisi lapangan
        if self.field_side == 'right':
            # Kotak penalti harus berada di sisi kanan
            rightmost_x = max(p[0] for p in field_points)
            return rightmost_x > 0
        else:
            # Kotak penalti harus berada di sisi kiri
            leftmost_x = min(p[0] for p in field_points)
            return leftmost_x < 0

    def process_contours(self, contours, image_shape):
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Calculate relative position on field
        center_x = (x + w/2) / image_shape[1]
        center_y = (y + h/2) / image_shape[0]
        
        estimated_x = (center_x - 0.5) * self.field_length
        estimated_y = (center_y - 0.5) * self.field_width
        
        self.update_particles_with_vision(estimated_x, estimated_y)

    def update_particles_with_vision(self, estimated_x, estimated_y):
        # Update particles with vision information (weighted update)
        if not self.is_position_confirmed:
            self.reinitialize_if_needed()
            return
            
        for i in range(len(self.particles)):
            x, y, theta = self.particles[i]
            
            # Bobot update berdasarkan jarak dari posisi awal terverifikasi
            if hasattr(self, 'initial_verified_pose'):
                dist_from_init = math.sqrt((x - self.initial_verified_pose[0])**2 + 
                                         (y - self.initial_verified_pose[1])**2)
                weight = 1.0 / (1.0 + dist_from_init)  # Makin jauh makin kecil bobotnya
            else:
                weight = 0.1
            
            # Update posisi dengan pembobotan
            new_x = x * (1 - weight) + estimated_x * weight
            new_y = y * (1 - weight) + estimated_y * weight
            
            # Terapkan batasan sisi lapangan
            if self.field_side == 'right':
                new_x = max(0, new_x)
            else:
                new_x = min(0, new_x)
                
            self.particles[i] = (new_x, new_y, theta)
    
    def visualize_image_processing(self, original, mask_green, mask_white, combined_mask):
        # Create visualization image
        vis_image = np.zeros((original.shape[0]*2, original.shape[1]*2, 3), dtype=np.uint8)
        
        # Original image
        vis_image[:original.shape[0], :original.shape[1]] = original
        
        # Green mask
        green_vis = cv2.cvtColor(mask_green, cv2.COLOR_GRAY2BGR)
        vis_image[:original.shape[0], original.shape[1]:original.shape[1]*2] = green_vis
        
        # White mask
        white_vis = cv2.cvtColor(mask_white, cv2.COLOR_GRAY2BGR)
        vis_image[original.shape[0]:original.shape[0]*2, :original.shape[1]] = white_vis
        
        # Combined mask
        combined_vis = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
        vis_image[original.shape[0]:original.shape[0]*2, original.shape[1]:original.shape[1]*2] = combined_vis
        
        # Add labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(vis_image, 'Original', (10, 20), font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(vis_image, 'Green Mask', (original.shape[1]+10, 20), font, 0.5, (255, 255, 255), 1)
        cv2.putText(vis_image, 'White Mask', (10, original.shape[0]+20), font, 0.5, (255, 255, 255), 1)
        cv2.putText(vis_image, 'Combined', (original.shape[1]+10, original.shape[0]+20), font, 0.5, (255, 255, 255), 1)
        
        # cv2.imshow(self.image_processing_window, vis_image)
        # cv2.waitKey(1)

    def calculate_distance(self, point, image_shape):
        """
        Improved distance calculation using camera parameters
        """
        height, width = image_shape[:2]

        # Camera parameters (adjust sesuai dengan kamera robot)
        CAMERA_HEIGHT = 0.45  # meters
        CAMERA_TILT = math.radians(15)  # camera tilt angle
        FOCAL_LENGTH = 650  # pixels

        # Convert to normalized coordinates
        normalized_y = (point[1] - height/2) / height

        # Calculate angle from image center
        pixel_y_from_center = point[1] - height/2
        angle = math.atan2(pixel_y_from_center, FOCAL_LENGTH)

        # Calculate real distance considering camera parameters
        total_angle = CAMERA_TILT + angle
        if abs(total_angle) < 1e-6:
            return float('inf')

        distance = CAMERA_HEIGHT / math.tan(total_angle)

        # Apply correction factors
        distance = self.apply_distance_corrections(distance, normalized_y)

        return distance

    def apply_distance_corrections(self, distance, normalized_y):
        """
        Apply various corrections to improve distance estimation
        """
        # Correction based on vertical position in image
        vertical_factor = 1.0 + abs(normalized_y) * 0.2

        # Non-linear correction for far distances
        if distance > 2.0:
            distance *= 0.85  # Reduce overestimation for far objects

        # Apply perspective correction
        distance *= vertical_factor

        return distance

    def update_particles_with_odometry(self):
        """
        Update particles berdasarkan odometri yang diperbaiki
        """
        if not hasattr(self, 'particles') or not self.particles:
            return

        # Hitung perubahan odometri
        dx, dy, dtheta = self.calculate_odometry()

        if dx == 0 and dy == 0 and dtheta == 0:
            return

        # Update setiap partikel
        for i in range(len(self.particles)):
            x, y, theta, weight = self.particles[i]

            # Tambahkan noise yang proporsional dengan pergerakan
            dx_noise = np.random.normal(0, abs(dx) * 0.1)
            dy_noise = np.random.normal(0, abs(dy) * 0.1)
            dtheta_noise = np.random.normal(0, abs(dtheta) * 0.1)

            # Transformasi ke koordinat global
            cos_theta = math.cos(theta)
            sin_theta = math.sin(theta)

            # Perhitungan pergerakan yang diperbarui
            if self.field_side == 'right':
                global_dx = (dx + dx_noise) * cos_theta - (dy + dy_noise) * sin_theta
                global_dy = (dx + dx_noise) * sin_theta + (dy + dy_noise) * cos_theta
            else:
                global_dx = -((dx + dx_noise) * cos_theta - (dy + dy_noise) * sin_theta)
                global_dy = -((dx + dx_noise) * sin_theta + (dy + dy_noise) * cos_theta)

            # Update posisi
            new_x = x + global_dx
            new_y = y + global_dy
            new_theta = theta + (dtheta + dtheta_noise)

            # Normalisasi sudut
            new_theta = math.atan2(math.sin(new_theta), math.cos(new_theta))

            # Terapkan batas lapangan
            new_x = max(min(new_x, self.field_length/2), -self.field_length/2)
            new_y = max(min(new_y, self.field_width/2), -self.field_width/2)

            # Update weight berdasarkan seberapa valid pergerakan
            movement_confidence = self.calculate_motion_confidence(dx, dy)
            new_weight = weight * movement_confidence

            # Update partikel
            self.particles[i] = [new_x, new_y, new_theta, new_weight]

        # Normalize weights
        total_weight = sum(p[3] for p in self.particles)
        if total_weight > 0:
            for i in range(len(self.particles)):
                self.particles[i][3] /= total_weight

        # Resample jika weights terlalu kecil
        if total_weight < 0.1:
            self.resample_particles()

    def detect_walking_phase(self, leg_prefix):
        """
        Deteksi fase walking yang lebih akurat
        """
        try:
            if self.current_joint_states is None:
                return 'unknown'

            # Get joint positions
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

            # Phase detection dengan threshold yang disesuaikan
            if knee_val < 0.2 and ank_val < 0.15:
                return 'stance'
            elif knee_val > 0.3 or hip_pitch_val > 0.25:
                return 'swing'
            else:
                return 'transition'

        except Exception as e:
            self.get_logger().warn(f"Error in detect_walking_phase: {str(e)}")
            return 'unknown'
    
    def is_walking(self):
        """
        Deteksi apakah robot sedang berjalan dengan menganalisa fase kedua kaki
        Returns:
            bool: True jika robot terdeteksi sedang berjalan
        """
        try:
            # Deteksi fase untuk kedua kaki
            right_phase = self.detect_walking_phase('r')
            left_phase = self.detect_walking_phase('l')
            
            # Dapatkan nilai velocity dari joint states
            right_velocities = []
            left_velocities = []
            
            if self.current_joint_states:
                for i, name in enumerate(self.current_joint_states.name):
                    if name.startswith('r_'):
                        right_velocities.append(abs(self.current_joint_states.velocity[i]))
                    elif name.startswith('l_'):
                        left_velocities.append(abs(self.current_joint_states.velocity[i]))
            
            # Hitung rata-rata velocity untuk kedua kaki
            avg_right_vel = sum(right_velocities) / len(right_velocities) if right_velocities else 0
            avg_left_vel = sum(left_velocities) / len(left_velocities) if left_velocities else 0
            
            # Kriteria walking:
            # 1. Fase kaki harus berbeda (satu stance, satu swing)
            # 2. Ada pergerakan yang signifikan (velocity > threshold)
            # 3. Kedua kaki aktif bergerak
            
            is_phases_alternating = (
                (right_phase == 'stance' and left_phase == 'swing') or
                (right_phase == 'swing' and left_phase == 'stance')
            )
            
            velocity_threshold = 0.1  # Sesuaikan dengan karakteristik robot
            is_significant_movement = (
                avg_right_vel > velocity_threshold or 
                avg_left_vel > velocity_threshold
            )
            
            is_both_legs_active = (
                right_phase != 'unknown' and 
                left_phase != 'unknown' and
                not (right_phase == 'transition' and left_phase == 'transition')
            )
            
            return is_phases_alternating and is_significant_movement and is_both_legs_active
    
        except Exception as e:
            self.get_logger().warn(f"Error in is_walking detection: {str(e)}")
            return False
    
    def get_walking_status(self):
        """
        Dapatkan status detail walking robot
        Returns:
            dict: Status detail walking robot
        """
        right_phase = self.detect_walking_phase('r')
        left_phase = self.detect_walking_phase('l')
        
        status = {
            'is_walking': self.is_walking(),
            'right_leg': {
                'phase': right_phase,
                'joints': {
                    'ank_pitch': 0.0,
                    'knee': 0.0,
                    'hip_pitch': 0.0
                }
            },
            'left_leg': {
                'phase': left_phase,
                'joints': {
                    'ank_pitch': 0.0,
                    'knee': 0.0,
                    'hip_pitch': 0.0
                }
            }
        }
        
        # Update nilai joint jika tersedia
        if self.current_joint_states:
            for i, name in enumerate(self.current_joint_states.name):
                if name.startswith('r_'):
                    joint_name = name.replace('r_', '')
                    if joint_name in status['right_leg']['joints']:
                        status['right_leg']['joints'][joint_name] = self.current_joint_states.position[i]
                elif name.startswith('l_'):
                    joint_name = name.replace('l_', '')
                    if joint_name in status['left_leg']['joints']:
                        status['left_leg']['joints'][joint_name] = self.current_joint_states.position[i]
        
        return status
    def calculate_odometry(self):
        """
        Calculate odometry based on joint movements with improved sensitivity
        """
        try:
            if self.previous_joint_states is None or self.current_joint_states is None:
                return 0.0, 0.0, 0.0

            t_curr = Time.from_msg(self.current_joint_states.header.stamp)
            t_prev = Time.from_msg(self.previous_joint_states.header.stamp)
            dt = (t_curr.nanoseconds - t_prev.nanoseconds) / 1e9
            if dt <= 0:
                return 0.0, 0.0, 0.0

            # Get joint indices
            joint_indices = {}
            for joint in ['r_hip_pitch', 'l_hip_pitch', 
                         'r_knee', 'l_knee',
                         'r_ank_pitch', 'l_ank_pitch',
                         'r_hip_roll', 'l_hip_roll']:
                try:
                    joint_indices[joint] = self.current_joint_states.name.index(joint)
                except ValueError:
                    self.get_logger().warn(f"Joint {joint} not found")
                    return 0.0, 0.0, 0.0

            # Get current and previous joint positions
            current_positions = {
                joint: self.current_joint_states.position[idx]
                for joint, idx in joint_indices.items()
            }
            previous_positions = {
                joint: self.previous_joint_states.position[idx]
                for joint, idx in joint_indices.items()
            }

            # Calculate joint changes
            joint_changes = {
                joint: abs(current_positions[joint] - previous_positions[joint])
                for joint in joint_indices.keys()
            }

            # Define movement thresholds (lowered for better sensitivity)
            KNEE_THRESHOLD = 0.003  # Reduced from 0.3
            ANKLE_THRESHOLD = 0.010  # Reduced from 0.18
            HIP_ROLL_THRESHOLD = 0.01  # New threshold for rotation detection

            # Detect leg phases
            right_moving = (joint_changes['r_knee'] > KNEE_THRESHOLD or 
                           joint_changes['r_ank_pitch'] > ANKLE_THRESHOLD)
            left_moving = (joint_changes['l_knee'] > KNEE_THRESHOLD or 
                          joint_changes['l_ank_pitch'] > ANKLE_THRESHOLD)

            # Initialize movement variables
            dx = 0.0
            dy = 0.0
            dtheta = 0.0

            # Calculate forward movement (dx)
            if right_moving or left_moving:
                # Base step size (increased for better movement)
                step_size = 0.04  # Increased from previous value

                # Adjust step size based on joint movement magnitude
                knee_movement = max(joint_changes['r_knee'], joint_changes['l_knee'])
                ankle_movement = max(joint_changes['r_ank_pitch'], joint_changes['l_ank_pitch'])
                movement_scale = (knee_movement + ankle_movement) / (KNEE_THRESHOLD + ANKLE_THRESHOLD)

                dx = step_size * movement_scale

            # Calculate lateral movement (dy)
            hip_roll_diff = (joint_changes['r_hip_roll'] - joint_changes['l_hip_roll'])
            if abs(hip_roll_diff) > HIP_ROLL_THRESHOLD:
                dy = 0.02 * np.sign(hip_roll_diff)  # Lateral step size

            # Calculate rotation (dtheta)
            hip_pitch_diff = (joint_changes['r_hip_pitch'] - joint_changes['l_hip_pitch'])
            if abs(hip_pitch_diff) > HIP_ROLL_THRESHOLD:
                dtheta = 0.1 * np.sign(hip_pitch_diff)  # Rotation step size

            # Scale movements by time
            time_scale = min(dt * 2.0, 1.0)  # Limit maximum scaling
            dx *= time_scale
            dy *= time_scale
            dtheta *= time_scale

            # Apply additional scaling based on walking parameters
            if hasattr(self, 'walking_params'):
                dx *= self.walking_params['step_forward_back_ratio']
                dy *= self.walking_params['swing_right_left']

            # Smooth the movements
            if not hasattr(self, 'odometry_buffer'):
                self.odometry_buffer = {
                    'dx': collections.deque(maxlen=3),
                    'dy': collections.deque(maxlen=3),
                    'dtheta': collections.deque(maxlen=3)
                }

            self.odometry_buffer['dx'].append(dx)
            self.odometry_buffer['dy'].append(dy)
            self.odometry_buffer['dtheta'].append(dtheta)

            dx = sum(self.odometry_buffer['dx']) / len(self.odometry_buffer['dx'])
            dy = sum(self.odometry_buffer['dy']) / len(self.odometry_buffer['dy'])
            dtheta = sum(self.odometry_buffer['dtheta']) / len(self.odometry_buffer['dtheta'])

            # Log the final odometry values
            self.get_logger().info(f"Final odometry - dx: {dx:.4f}, dy: {dy:.4f}, dtheta: {dtheta:.4f}")

            return dx, dy, dtheta

        except Exception as e:
            self.get_logger().warn(f"Error in calculate_odometry: {str(e)}")
            return 0.0, 0.0, 0.0

            
    def get_joint_changes(prefix):
        changes = {}
        for joint in ['ank_pitch', 'knee', 'hip_pitch', 'hip_yaw']:
            joint_name = f'{prefix}_{joint}'
            try:
                curr_idx = self.current_joint_states.name.index(joint_name)
                prev_idx = self.previous_joint_states.name.index(joint_name)
                curr_pos = self.current_joint_states.position[curr_idx]
                prev_pos = self.previous_joint_states.position[prev_idx]
                # Simpan nilai absolut dan arah perubahan
                changes[joint] = {
                    'magnitude': abs(curr_pos - prev_pos),
                    'direction': 1 if curr_pos > prev_pos else -1
                }
            except (ValueError, IndexError):
                changes[joint] = {'magnitude': 0.0, 'direction': 0}
        return changes
    def is_leg_moving(changes):
        return sum(change['magnitude'] for change in changes.values()) > JOINT_MOVEMENT_THRESHOLD
    def smooth_odometry(self, dx, dy, dtheta):
        """
        Smoothing odometry menggunakan moving average
        """
        if not hasattr(self, 'odometry_buffer'):
            self.odometry_buffer = {
                'dx': collections.deque(maxlen=3),
                'dy': collections.deque(maxlen=3),
                'dtheta': collections.deque(maxlen=3)
            }

        self.odometry_buffer['dx'].append(dx)
        self.odometry_buffer['dy'].append(dy)
        self.odometry_buffer['dtheta'].append(dtheta)

        dx = sum(self.odometry_buffer['dx']) / len(self.odometry_buffer['dx'])
        dy = sum(self.odometry_buffer['dy']) / len(self.odometry_buffer['dy'])
        dtheta = sum(self.odometry_buffer['dtheta']) / len(self.odometry_buffer['dtheta'])

        return dx, dy, dtheta


    def point_to_line_segment_distance(self, px, py, p1, p2):
        """
        Calculate distance from point (px,py) to line segment (p1,p2)
        """
        x1, y1 = p1
        x2, y2 = p2

        # Calculate squared length of line segment
        line_length_sq = (x2 - x1)**2 + (y2 - y1)**2

        # If line segment has zero length, return distance to p1
        if line_length_sq == 0:
            return math.sqrt((px - x1)**2 + (py - y1)**2)

        # Calculate projection point parameter
        t = ((px - x1)*(x2 - x1) + (py - y1)*(y2 - y1)) / line_length_sq

        if t < 0:  # Point projects beyond p1
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        elif t > 1:  # Point projects beyond p2
            return math.sqrt((px - x2)**2 + (py - y2)**2)
        else:  # Point projects onto line segment
            # Calculate projection point
            proj_x = x1 + t*(x2 - x1)
            proj_y = y1 + t*(y2 - y1)
            return math.sqrt((px - proj_x)**2 + (py - proj_y)**2)
        
    def distance_to_center_circle(self, x, y, circle):
        """
        Calculate distance from point to center circle
        """
        cx, cy, radius = circle

        # Convert image coordinates to field coordinates
        field_x = (cx - self.image_width/2) * self.field_length/self.image_width
        field_y = (cy - self.image_height/2) * self.field_width/self.image_height
        field_radius = radius * self.field_length/self.image_width

        # Calculate distance to circle center
        dist_to_center = math.sqrt((x - field_x)**2 + (y - field_y)**2)

        # Return absolute difference from expected radius
        return abs(dist_to_center - field_radius)

    def distance_to_field_line(self, x, y, line):
        """
        Calculate distance from point to field line
        """
        if 'endpoints' not in line or line['endpoints'] is None:
            return float('inf')

        p1, p2 = line['endpoints']

        # Convert image coordinates to field coordinates
        field_p1_x = (p1[0] - self.image_width/2) * self.field_length/self.image_width
        field_p1_y = (p1[1] - self.image_height/2) * self.field_width/self.image_height
        field_p2_x = (p2[0] - self.image_width/2) * self.field_length/self.image_width
        field_p2_y = (p2[1] - self.image_height/2) * self.field_width/self.image_height

        return self.point_to_line_segment_distance(x, y, 
                                                 (field_p1_x, field_p1_y),
                                                 (field_p2_x, field_p2_y))

    def distance_to_field_features(self, x, y):
        """
        Calculate minimum distance to known field features
        """
        min_dist = float('inf')

        # Distance to center line
        center_line_dist = abs(x)
        min_dist = min(min_dist, center_line_dist)

        # Distance to side lines
        side_line_dist = min(abs(y - self.field_width/2), 
                            abs(y + self.field_width/2))
        min_dist = min(min_dist, side_line_dist)

        # Distance to end lines
        end_line_dist = min(abs(x - self.field_length/2), 
                           abs(x + self.field_length/2))
        min_dist = min(min_dist, end_line_dist)

        return min_dist

    def calculate_phase_based_confidence(self, support_phase, left_movement, right_movement):
        """
        Calculate confidence based on walking phase and movement symmetry
        """
        # Check movement symmetry
        total_movement = left_movement + right_movement
        if total_movement == 0:
            return 1.0

        movement_symmetry = min(left_movement, right_movement) / (total_movement/2)

        # Higher confidence during support phases
        phase_confidence = 1.0 if support_phase is not None else 0.8

        # Combine factors
        confidence = movement_symmetry * phase_confidence

        # Limit confidence range
        return max(0.6, min(1.0, confidence))
    
    def calculate_motion_confidence(self, dx, dy):
        """Calculate confidence factor for motion estimation"""
        if not hasattr(self, 'motion_history') or len(self.motion_history) < 2:
            return 1.0
            
        # Check consistency with recent motion
        recent_dx = sum(m['dx'] for m in self.motion_history[-5:]) / 5 if len(self.motion_history) >= 5 else dx
        recent_dy = sum(m['dy'] for m in self.motion_history[-5:]) / 5 if len(self.motion_history) >= 5 else dy
        
        # Calculate deviation from recent average
        dx_deviation = abs(dx - recent_dx) / (abs(recent_dx) + 1e-6)
        dy_deviation = abs(dy - recent_dy) / (abs(recent_dy) + 1e-6)
        
        # Higher deviation means lower confidence
        confidence = 1.0 / (1.0 + dx_deviation + dy_deviation)
        
        return max(0.5, min(1.0, confidence))  # Limit confidence between 0.5 and 1.0


    def estimate_pose(self):
        """Estimate the robot's pose from particle distribution"""
        if len(self.particles) == 0:
            return (0, 0, 0)

        # Calculate weighted mean position
        total_weight = sum(p[3] for p in self.particles)
        if total_weight == 0:
            # If all weights are zero, use simple mean
            x = np.mean([p[0] for p in self.particles])
            y = np.mean([p[1] for p in self.particles])
        else:
            # Use weighted mean
            x = sum(p[0] * p[3] for p in self.particles) / total_weight
            y = sum(p[1] * p[3] for p in self.particles) / total_weight

        # Use direct yaw measurement for orientation
        theta = self.yaw

        return (x, y, theta)

    def calibrate_orientation(self):
        """
        Calibrate initial robot orientation - FIXED orientation logic
        """
        if not hasattr(self, 'orientation_calibration_count'):
            self.orientation_calibration_count = 0
            self.orientation_samples = []

        # Collect several orientation samples
        if self.orientation_calibration_count < 10:
            self.orientation_samples.append(self.yaw)
            self.orientation_calibration_count += 1
            return False

        # Calculate median orientation
        median_orientation = sorted(self.orientation_samples)[len(self.orientation_samples)//2]

        # Set initial orientation offset - FIXED: Reversed the logic
        if self.field_side == 'right':
            expected_orientation = 0.0  # Facing +X direction
        else:
            expected_orientation = math.pi  # Facing -X direction

        # Apply correction
        self.yaw_offset = median_orientation - expected_orientation

        return True

    def publish_pose(self):
        """Publish the estimated pose"""
        pose = self.estimate_pose()
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        
        # Set position
        msg.pose.pose.position.x = pose[0]
        msg.pose.pose.position.y = pose[1]
        msg.pose.pose.position.z = 0.0
        
        # Convert orientation to quaternion
                cy = math.cos(pose[2] * 0.5)
        sy = math.sin(pose[2] * 0.5)
        cp = math.cos(0 * 0.5)
        sp = math.sin(0 * 0.5)
        cr = math.cos(0 * 0.5)
        sr = math.sin(0 * 0.5)
        q = [
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy
        ]
        msg.pose.pose.orientation.x = q[0]
        msg.pose.pose.orientation.y = q[1]
        msg.pose.pose.orientation.z = q[2]
        msg.pose.pose.orientation.w = q[3]
        
        # Set covariance matrix
        covariance = [0.0] * 36
        # Position covariance
        covariance[0] = 0.1  # x
        covariance[7] = 0.1  # y
        covariance[14] = 0.1 # z
        # Rotation covariance
        covariance[21] = 0.1 # roll
        covariance[28] = 0.1 # pitch
        covariance[35] = 0.05 # yaw - smaller because we're more confident in orientation sensor
        
        msg.pose.covariance = covariance
        
        # Publish the pose
        self.pose_pub.publish(msg)
        
        # Broadcast transform
        self.tf_broadcaster.sendTransform(
            (pose[0], pose[1], 0),  # translation
            q,                      # rotation
            self.get_clock().now().to_msg(),
            "base_footprint",
            "map"
        )

    def visualize(self):
        """Visualize the localization state"""
        # Clear visualization
        self.field_image.fill(0)
        
        # Draw field lines
        height, width = self.field_image.shape[:2]
        
        # Field borders
        cv2.rectangle(self.field_image, 
                     (int(width*0.1), int(height*0.1)),
                     (int(width*0.9), int(height*0.9)),
                     (255, 255, 255), 2)
        
        # Center line
        cv2.line(self.field_image,
                 (int(width/2), int(height*0.1)),
                 (int(width/2), int(height*0.9)),
                 (255, 255, 255), 2)
        
        # Center circle
        center = (int(width/2), int(height/2))
        radius = int(min(width, height) * 0.15)
        cv2.circle(self.field_image, center, radius, (255, 255, 255), 2)
        
        # Draw particles
        for p in self.particles:
            x = int((p[0] + self.field_length/2) * width/self.field_length)
            y = int((p[1] + self.field_width/2) * height/self.field_width)
            
            if 0 <= x < width and 0 <= y < height:
                cv2.circle(self.field_image, (x, y), 1, (0, 255, 0), -1)
        
        # Draw robot pose
        pose = self.estimate_pose()
        robot_x = int((pose[0] + self.field_length/2) * width/self.field_length)
        robot_y = int((pose[1] + self.field_width/2) * height/self.field_width)
        
        if 0 <= robot_x < width and 0 <= robot_y < height:
            # Robot position
            cv2.circle(self.field_image, (robot_x, robot_y), 5, (0, 0, 255), -1)
            
            # Robot orientation
            arrow_length = 20
            arrow_x = robot_x + int(arrow_length * math.cos(pose[2]))
            arrow_y = robot_y - int(arrow_length * math.sin(pose[2]))
            
            cv2.arrowedLine(self.field_image, 
                           (robot_x, robot_y),
                           (arrow_x, arrow_y),
                           (0, 0, 255), 2)

        # Draw detected objects
        self.draw_detected_objects()
        
        # Add text information
        self.add_visualization_text(pose)
        
        # Show visualization
        # cv2.imshow(self.visualization_window_name, self.field_image)
        # cv2.waitKey(1)

    def draw_detected_objects(self):
        """Draw detected objects (ball, goal, landmarks) on visualization"""
        height, width = self.field_image.shape[:2]
    
        # Draw robot position
        robot_pose = self.estimate_pose()
        robot_x = int((robot_pose[0] + self.field_length/2) * width/self.field_length)
        robot_y = int((robot_pose[1] + self.field_width/2) * height/self.field_width)
        cv2.circle(self.field_image, (robot_x, robot_y), 5, (0, 0, 255), -1)
    
        # Draw detection radius
        detection_radius = int(2.0 * width/self.field_length)  # 2 meter radius
        cv2.circle(self.field_image, (robot_x, robot_y), detection_radius, (0, 255, 0), 1)
    
        # Draw ball if detected
        try:
            if self.ball_position is not None and isinstance(self.ball_position, tuple) and len(self.ball_position) >= 3:
                # Convert ball position to visualization coordinates
                ball_x = int((self.ball_position[0] + self.field_length/2) * width/self.field_length)
                ball_y = int((self.ball_position[1] + self.field_width/2) * height/self.field_width)
                
                if 0 <= ball_x < width and 0 <= ball_y < height:
                    # Draw ball
                    cv2.circle(self.field_image, (ball_x, ball_y), 4, (0, 255, 255), -1)
                    
                    # Draw line from robot to ball
                    cv2.line(self.field_image, (robot_x, robot_y), (ball_x, ball_y), (0, 255, 255), 1)
                    
                    # Draw distance and position information
                    cv2.putText(self.field_image,
                              f"Ball distance: {self.ball_position[2]:.2f}m",
                              (10, height - 40),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    
                    cv2.putText(self.field_image,
                              f"Ball pos: ({self.ball_position[0]:.2f}, {self.ball_position[1]:.2f})",
                              (10, height - 20),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    
                    # Add relative position indicators
                    rel_x = ball_x - robot_x
                    rel_y = ball_y - robot_y
                    cv2.putText(self.field_image,
                              f"Relative: dx={rel_x/width*self.field_length:.2f}m, dy={rel_y/height*self.field_width:.2f}m",
                              (10, height - 60),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        except Exception as e:
            self.get_logger().warn(f"Error drawing ball position: {e}")
            # Optional: Draw a message indicating ball detection error
            cv2.putText(self.field_image,
                      "Ball detection error",
                      (10, height - 20),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
        # Draw other landmarks if needed
        try:
            if hasattr(self, 'detected_landmarks') and self.detected_landmarks:
                for landmark in self.detected_landmarks:
                    if hasattr(landmark, 'x') and hasattr(landmark, 'y'):
                        landmark_x = int((landmark.x + self.field_length/2) * width/self.field_length)
                        landmark_y = int((landmark.y + self.field_width/2) * height/self.field_width)
                        if 0 <= landmark_x < width and 0 <= landmark_y < height:
                            cv2.circle(self.field_image, (landmark_x, landmark_y), 3, (255, 0, 0), -1)
        except Exception as e:
            self.get_logger().warn(f"Error drawing landmarks: {e}")
    
    def add_visualization_text(self, pose):
        """Add text information to visualization"""
        height = self.field_image.shape[0]
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_color = (255, 255, 255)
        line_type = 1
        
        # Show robot pose
        cv2.putText(self.field_image,
                   f"Robot Position: ({pose[0]:.2f}, {pose[1]:.2f})",
                   (10, 20), font, font_scale, font_color, line_type)
        
        # Show orientation
        cv2.putText(self.field_image,
                   f"Orientation: {math.degrees(pose[2]):.1f} deg",
                   (10, 40), font, font_scale, font_color, line_type)
        
        # Show ball position if available
        if self.ball_position is not None:
            cv2.putText(self.field_image,
                       f"Ball: ({self.ball_position[0]:.2f}, {self.ball_position[1]:.2f})",
                       (10, 60), font, font_scale, (0, 255, 255), line_type)
        else:
            cv2.putText(self.field_image,
                       "Ball: Not detected",
                       (10, 60), font, font_scale, (0, 255, 255), line_type)
        
        # Show goal position if available
        if self.ball_position is not None:
            cv2.putText(self.field_image,
                   f"Ball detected at {self.ball_position[2]:.2f}m",
                   (10, 60), font, font_scale, (0, 255, 255), line_type)
        else:
            cv2.putText(self.field_image,
                   "Ball: Not detected",
                   (10, 60), font, font_scale, (0, 255, 255), line_type)
        if hasattr(self, 'field_orientation') and self.field_orientation:
                cv2.putText(self.field_image,
               f"Field Orientation: {self.field_orientation}",
               (10, 80), font, font_scale, font_color, line_type)

    def run_step(self):
        # Tentukan orientasi lapangan
        self.determine_field_orientation()
        # Update dan publish pose
        self.publish_pose()
        self.visualize()
        if self.field_orientation and not self.is_orientation_confirmed:
            self.get_logger().info(f"Field orientation determined: {self.field_orientation}")
            self.is_orientation_confirmed = True
if __name__ == '__main__':
    try:
        # Create custom message type for orientation
        from std_msgs.msg import Header
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--side', type=str, default='right',
                          choices=['right', 'left'],
                          help='Field side to initialize (right or left)')
        args = parser.parse_args()
        
        # Initialize and run localization with specified side
        localization = ImprovedOP3Localization(field_side=args.side)
        localization.run()
        
    except Exception:
        pass
    except Exception as e:
        self.get_logger().error(f"Error in OP3 Localization: {str(e)}")
        raise
