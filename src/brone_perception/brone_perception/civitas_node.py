#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Point
from sensor_msgs.msg import Image
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from cv_bridge import CvBridge
import json
import cv2
import os
import sys

_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PKG_DIR)
from lib.civitas.detection import JetsonCivitasSystem

class CivitasNode(Node):
    def __init__(self):
        super().__init__('civitas_perception_node')
        
        self.civitas_pub = self.create_publisher(String, '/brone/perception/civitas', 10)
        self.target_pub = self.create_publisher(Point, '/brone/perception/target', 10)
        
        self.cmd_sub = self.create_subscription(String, '/brone/module_control', self.on_command, 10)
        
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.image_sub = self.create_subscription(Image, '/brone/camera/image_raw', self.image_callback, qos_profile)
        
        self.bridge = CvBridge()
        self.system = JetsonCivitasSystem()
        self.active = False

    def on_command(self, msg):
        try:
            data = json.loads(msg.data)
            if data.get('module') == 'civitas':
                state = data.get('state')
                self.active = (state == 'start')
                self.get_logger().info(f'[Civitas Node] Active state set to {self.active}')
        except Exception as e:
            self.get_logger().error(f'Command parse error: {e}')

    def image_callback(self, msg):
        if not self.active:
            return
            
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            self.get_logger().error(f'CV Bridge error: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.system.brightness.update(gray)
        
        faces = self.system.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(100, 100)
        )

        tracked_faces = self.system.face_tracker.update(faces, frame)
        
        if tracked_faces:
            largest_face = max(tracked_faces, key=lambda f: f[3]*f[4])
            tid, x, y, w, h = largest_face
            
            point_msg = Point()
            point_msg.x = float(x + w/2)
            point_msg.y = float(y + h/2)
            point_msg.z = float(w * h)
            self.target_pub.publish(point_msg)

            status, score, _, _ = self.system.civitas_detector.detect_civitas_status(
                frame, tid, x, y, w, h, self.system.scheduler, self.system.brightness)
            
            civitas_msg = String()
            civitas_msg.data = json.dumps({
                'id': tid,
                'status': status,
                'score': score
            })
            self.civitas_pub.publish(civitas_msg)

def main(args=None):
    rclpy.init(args=args)
    node = CivitasNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
