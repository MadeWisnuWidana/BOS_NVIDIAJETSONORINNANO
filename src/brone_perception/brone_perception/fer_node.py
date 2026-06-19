#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import numpy as np
import onnxruntime as ort
import mediapipe as mp
import paho.mqtt.client as mqtt
import json
import time
from collections import deque
import os

# Configuration
class Config:
    MODEL_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
        "fer_v2/models/fer_resnet34_v1.2.onnx"
    )
    INPUT_SIZE = 224
    EMOTION_LABELS = ['Upset', 'Shocked', 'Happy', 'Sad', 'Neutral']
    WINDOW_SIZE = 15
    CONFIDENCE_THRESHOLD = 0.5
    MQTT_BROKER = "localhost"
    MQTT_PORT = 1883
    MQTT_TOPIC_GAZE = "robot/fer_gaze"

class TemporalAveraging:
    def __init__(self, window_size=15, confidence_threshold=0.5):
        self.window_size = window_size
        self.confidence_threshold = confidence_threshold
        self.buffer = deque(maxlen=window_size)

    def add_prediction(self, probabilities):
        self.buffer.append(probabilities)

    def get_averaged_emotion(self):
        if len(self.buffer) < 2:
            return "Collecting...", 0.0
        avg_probs = np.mean(self.buffer, axis=0)
        idx = np.argmax(avg_probs)
        conf = np.max(avg_probs)
        if conf >= self.confidence_threshold:
            return Config.EMOTION_LABELS[idx], conf
        return "UNCERTAIN", conf

    def reset(self):
        self.buffer.clear()

class FERNode(Node):
    def __init__(self):
        super().__init__('fer_node')
        self.get_logger().info('Starting FER Node (ROS 2 Subscriber)...')
        
        self.active = False
        self.cmd_sub = self.create_subscription(String, '/brone/module_control', self.control_callback, 10)
        
        # ROS 2 Publisher for expression (to Arbitrator)
        self.expr_pub = self.create_publisher(String, '/brone/fer_expression', 10)
        
        # Subscribe to camera with KEEP_LAST = 1 to prevent lag
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.image_sub = self.create_subscription(Image, '/brone/camera/image_raw', self.image_callback, qos_profile)
        self.bridge = CvBridge()
        
        self.setup_mqtt()
        self.load_model()
        self.setup_face_detection()
        
        self.temporal_avg = TemporalAveraging(Config.WINDOW_SIZE, Config.CONFIDENCE_THRESHOLD)
        self.no_face_counter = 0

    def control_callback(self, msg):
        try:
            data = json.loads(msg.data)
            if data.get('module') == 'fer':
                state = data.get('state')
                self.active = (state == 'start')
                self.get_logger().info(f'[FER Node] Active state set to {self.active}')
                if not self.active:
                    self.temporal_avg.reset()
        except Exception as e:
            self.get_logger().error(f'Control error: {e}')

    def setup_mqtt(self):
        try:
            self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            self.client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, 60)
            self.client.loop_start()
            self.get_logger().info("MQTT Connected for Gaze")
        except Exception as e:
            self.get_logger().error(f"MQTT Error: {e}")
            self.client = None

    def load_model(self):
        try:
            providers = ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
            self.ort_session = ort.InferenceSession(Config.MODEL_PATH, providers=providers)
            self.input_name = self.ort_session.get_inputs()[0].name
            self.get_logger().info(f"ONNX Model loaded from {Config.MODEL_PATH}")
        except Exception as e:
            self.get_logger().error(f"Failed to load ONNX model: {e}")

    def setup_face_detection(self):
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5)

    def preprocess_face(self, face_img):
        face_img = cv2.resize(face_img, (Config.INPUT_SIZE, Config.INPUT_SIZE))
        face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        face_img = face_img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        face_img = (face_img - mean) / std
        face_img = np.transpose(face_img, (2, 0, 1))
        return np.expand_dims(face_img, axis=0)

    def softmax(self, x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum(axis=1)

    def image_callback(self, msg):
        if not self.active:
            return
            
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f"CV Bridge Error: {e}")
            return
            
        frame_flip = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame_flip, cv2.COLOR_BGR2RGB)

        results = self.face_detection.process(rgb_frame)

        if results.detections:
            self.no_face_counter = 0
            best_detection = max(results.detections,
                key=lambda d: d.location_data.relative_bounding_box.width * d.location_data.relative_bounding_box.height)

            bboxC = best_detection.location_data.relative_bounding_box
            ih, iw, _ = frame_flip.shape

            center_x = bboxC.xmin + bboxC.width / 2
            center_y = bboxC.ymin + bboxC.height / 2
            gaze_x = (center_x - 0.5) * -2.0
            gaze_y = (center_y - 0.5) * 2.0

            x = int(bboxC.xmin * iw)
            y = int(bboxC.ymin * ih)
            w = int(bboxC.width * iw)
            h = int(bboxC.height * ih)

            x, y = max(0, x), max(0, y)
            w, h = min(iw - x, w), min(ih - y, h)

            if w > 0 and h > 0:
                face_roi = frame_flip[y:y+h, x:x+w]
                try:
                    input_tensor = self.preprocess_face(face_roi)
                    ort_outs = self.ort_session.run(None, {self.input_name: input_tensor})
                    probs = self.softmax(ort_outs[0])[0]

                    self.temporal_avg.add_prediction(probs)
                    emotion, confidence = self.temporal_avg.get_averaged_emotion()

                    # Publish Expression to ROS 2 Arbitrator
                    if emotion not in ["UNCERTAIN", "Collecting...", "Analyzing..."]:
                        emotion_mapping = {
                            'Upset': 'cry',
                            'Shocked': 'shock',
                            'Happy': 'happier',
                            'Sad': 'sad',
                            'Neutral': 'idle'
                        }
                        mapped_expr = emotion_mapping.get(emotion, 'idle')
                        expr_msg = String()
                        expr_msg.data = json.dumps({"expression": mapped_expr})
                        self.expr_pub.publish(expr_msg)

                    # Publish Gaze to MQTT
                    if self.client:
                        gaze_payload = {
                            "face_detected": True,
                            "gaze_x": gaze_x,
                            "gaze_y": gaze_y,
                            "timestamp": time.time()
                        }
                        self.client.publish(Config.MQTT_TOPIC_GAZE, json.dumps(gaze_payload))

                except Exception as e:
                    self.get_logger().error(f"Infer error: {e}")
        else:
            self.no_face_counter += 1
            if self.no_face_counter > 10:
                self.temporal_avg.reset()
                if self.client:
                    self.client.publish(Config.MQTT_TOPIC_GAZE, json.dumps({"face_detected": False}))

def main(args=None):
    rclpy.init(args=args)
    node = FERNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.client:
            node.client.loop_stop()
            node.client.disconnect()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
