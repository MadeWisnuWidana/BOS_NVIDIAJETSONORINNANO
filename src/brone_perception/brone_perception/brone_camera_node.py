#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2
import numpy as np
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy

class BroneCameraNode(Node):
    def __init__(self):
        super().__init__('brone_camera_node')
        
        # QoS Profile for Sensor Data (Best Effort)
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        self.publisher_ = self.create_publisher(CompressedImage, '/image_raw/compressed', qos_profile)
        self.timer = self.create_timer(1.0 / 30.0, self.timer_callback) # 30 FPS target
        
        self.cap = cv2.VideoCapture(0)
        # Optimasi kamera USB (Logitech Brio 4K)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        if not self.cap.isOpened():
            self.get_logger().error("Tidak dapat membuka kamera (/dev/video0)")
        
        self.bridge = CvBridge()
        self.get_logger().info("BRONE Camera Node berjalan. Mempublikasikan ke /image_raw")

    def timer_callback(self):
        if not self.cap.isOpened():
            return
            
        ret, frame = self.cap.read()
        if ret:
            # Kompres frame ke JPEG (~40 KB)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
            result, encimg = cv2.imencode('.jpg', frame, encode_param)
            
            if result:
                msg = CompressedImage()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.header.frame_id = "camera_link"
                msg.format = "jpeg"
                msg.data = np.array(encimg).tobytes()
                
                self.publisher_.publish(msg)

    def destroy_node(self):
        if self.cap.isOpened():
            self.cap.release()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = BroneCameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
