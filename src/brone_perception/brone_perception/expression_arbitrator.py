#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import paho.mqtt.client as mqtt
import json

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_EXPRESSION_TOPIC = "robot/expression"

class ExpressionArbitrator(Node):
    def __init__(self):
        super().__init__('expression_arbitrator')
        self.get_logger().info('[Arbitrator] Starting...')
        
        # ROS 2 Subscriptions
        self.fer_sub = self.create_subscription(String, '/brone/fer_expression', self.fer_callback, 10)
        self.vad_sub = self.create_subscription(String, '/brone/vad_expression', self.vad_callback, 10)
        
        # State
        self.is_speaking = False
        self.last_fer_expression = "idle"
        
        # MQTT Setup
        self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            self.get_logger().info("[Arbitrator] Connected to MQTT")
        except Exception as e:
            self.get_logger().error(f"[Arbitrator] MQTT Connection failed: {e}")

    def publish_mqtt(self, expression, duration=0):
        try:
            payload = json.dumps({"expression": expression, "duration": duration})
            self.mqtt_client.publish(MQTT_EXPRESSION_TOPIC, payload)
        except Exception as e:
            self.get_logger().error(f"[Arbitrator] Publish failed: {e}")

    def fer_callback(self, msg):
        try:
            data = json.loads(msg.data)
            expr = data.get("expression", "idle")
            
            # Cache the latest emotion
            self.last_fer_expression = expr
            
            # Only publish if NOT speaking
            if not self.is_speaking:
                self.publish_mqtt(expr)
        except Exception as e:
            self.get_logger().error(f"[Arbitrator] FER callback error: {e}")

    def vad_callback(self, msg):
        try:
            data = json.loads(msg.data)
            expr = data.get("expression", "idle")
            
            if expr == "speaking":
                if not self.is_speaking:
                    self.is_speaking = True
                    self.publish_mqtt("speaking")
            elif expr == "idle":
                if self.is_speaking:
                    self.is_speaking = False
                    # Restore the last facial emotion
                    self.publish_mqtt(self.last_fer_expression)
        except Exception as e:
            self.get_logger().error(f"[Arbitrator] VAD callback error: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = ExpressionArbitrator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.mqtt_client.loop_stop()
        node.mqtt_client.disconnect()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
