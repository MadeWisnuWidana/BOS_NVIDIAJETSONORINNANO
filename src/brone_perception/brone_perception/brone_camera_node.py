#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import json

class BroneCameraNode(Node):
    def __init__(self):
        super().__init__('brone_camera_server')
        self.get_logger().info('[Camera Server] Starting...')
        
        self.publisher = self.create_publisher(Image, '/brone/camera/image_raw', 10)
        self.cmd_sub = self.create_subscription(String, '/brone/module_control', self.control_callback, 10)
        
        self.bridge = CvBridge()
        self.cap = None
        self.timer = None
        
        # Track active modules
        self.active_modules = {
            'fer': False,
            'civitas': False
        }
        
    def control_callback(self, msg):
        try:
            data = json.loads(msg.data)
            module = data.get('module')
            state = data.get('state')
            
            if module in self.active_modules:
                self.active_modules[module] = (state == 'start')
                self.get_logger().info(f'[Camera Server] Module {module} state changed to {state}')
                self.check_camera_state()
        except Exception as e:
            self.get_logger().error(f'Error parsing control msg: {e}')
            
    def check_camera_state(self):
        # If any module needs camera, open it
        needs_camera = any(self.active_modules.values())
        
        if needs_camera and self.cap is None:
            self.get_logger().info('[Camera Server] Opening /dev/video0...')
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # Create timer to read frames at ~30 FPS
            self.timer = self.create_timer(1.0/30.0, self.publish_frame)
            
        elif not needs_camera and self.cap is not None:
            self.get_logger().info('[Camera Server] Releasing /dev/video0 (No active modules)...')
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.cap.release()
            self.cap = None
            
    def publish_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
                self.publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = BroneCameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.cap:
            node.cap.release()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
