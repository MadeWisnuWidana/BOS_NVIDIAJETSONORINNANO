#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray, String
import paho.mqtt.client as mqtt
import struct
import math
import json
import time

RMS_THRESHOLD = 300
SILENCE_TIMEOUT = 0.6
SPEAK_MIN_DURATION = 0.15

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_VAD_STATUS_TOPIC = "robot/vad_status"

def calc_rms(data_bytes):
    count = len(data_bytes) // 2
    if count == 0:
        return 0
    shorts = struct.unpack(f'{count}h', bytes(data_bytes))
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)

class VADNode(Node):
    def __init__(self):
        super().__init__('brone_vad_node')
        self.get_logger().info('Starting VAD Node (ROS 2 Audio Subscriber)...')
        
        self.active = False
        self.cmd_sub = self.create_subscription(String, '/brone/module_control', self.control_callback, 10)
        self.audio_sub = self.create_subscription(UInt8MultiArray, '/brone/audio/audio_raw', self.audio_callback, 10)
        
        self.expr_pub = self.create_publisher(String, '/brone/vad_expression', 10)
        
        self.is_speaking = False
        self.silence_start = None
        self.speak_start = None
        self.last_status_time = 0
        
        try:
            self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            self.get_logger().error(f"MQTT Error: {e}")
            self.client = None

    def control_callback(self, msg):
        try:
            data = json.loads(msg.data)
            if data.get('module') == 'vad':
                state = data.get('state')
                self.active = (state == 'start')
                self.get_logger().info(f'[VAD Node] Active state set to {self.active}')
                if not self.active:
                    self.reset_state()
        except Exception as e:
            self.get_logger().error(f'Control error: {e}')

    def reset_state(self):
        self.is_speaking = False
        self.silence_start = None
        self.speak_start = None
        msg = String()
        msg.data = json.dumps({"expression": "idle", "duration": 0})
        self.expr_pub.publish(msg)

    def audio_callback(self, msg):
        if not self.active:
            return
            
        data = msg.data
        rms = calc_rms(data)
        now = time.time()
        
        if rms >= RMS_THRESHOLD:
            self.silence_start = None
            if not self.is_speaking:
                if self.speak_start is None:
                    self.speak_start = now
                elif now - self.speak_start >= SPEAK_MIN_DURATION:
                    self.is_speaking = True
                    self.publish_state("speaking", rms, now)
        else:
            self.speak_start = None
            if self.is_speaking:
                if self.silence_start is None:
                    self.silence_start = now
                elif now - self.silence_start >= SILENCE_TIMEOUT:
                    self.is_speaking = False
                    self.publish_state("idle", rms, now)
        
        if now - self.last_status_time > 2.0:
            if self.client:
                self.client.publish(MQTT_VAD_STATUS_TOPIC, json.dumps({
                    "status": "speaking" if self.is_speaking else "silent",
                    "rms": round(rms, 1),
                    "timestamp_ms": int(now * 1000)
                }))
            self.last_status_time = now

    def publish_state(self, state, rms, now):
        expr_msg = String()
        expr_msg.data = json.dumps({"expression": state, "duration": 0})
        self.expr_pub.publish(expr_msg)
        
        if self.client:
            self.client.publish(MQTT_VAD_STATUS_TOPIC, json.dumps({
                "status": "speaking" if state == "speaking" else "silent", 
                "rms": round(rms, 1), 
                "timestamp_ms": int(now * 1000)
            }))

def main(args=None):
    rclpy.init(args=args)
    node = VADNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.reset_state()
        if node.client:
            node.client.loop_stop()
            node.client.disconnect()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
