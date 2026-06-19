#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray, String
import pyaudio
import json
import threading

# Audio Config
CHUNK = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000

class BroneAudioNode(Node):
    def __init__(self):
        super().__init__('brone_audio_server')
        self.get_logger().info('[Audio Server] Starting...')
        
        self.publisher = self.create_publisher(UInt8MultiArray, '/brone/audio/audio_raw', 10)
        self.cmd_sub = self.create_subscription(String, '/brone/module_control', self.control_callback, 10)
        
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.capture_thread = None
        
        self.active_modules = {
            'vad': False,
            'voice': False # SST/TTS
        }

    def control_callback(self, msg):
        try:
            data = json.loads(msg.data)
            module = data.get('module')
            state = data.get('state')
            
            if module in self.active_modules:
                self.active_modules[module] = (state == 'start')
                self.get_logger().info(f'[Audio Server] Module {module} state changed to {state}')
                self.check_audio_state()
        except Exception as e:
            self.get_logger().error(f'Error parsing control msg: {e}')

    def check_audio_state(self):
        needs_audio = any(self.active_modules.values())
        
        if needs_audio and not self.is_recording:
            self.get_logger().info('[Audio Server] Opening Microphone...')
            try:
                self.stream = self.pa.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                self.is_recording = True
                self.capture_thread = threading.Thread(target=self.capture_loop)
                self.capture_thread.start()
            except Exception as e:
                self.get_logger().error(f'[Audio Server] Failed to open mic: {e}')
                
        elif not needs_audio and self.is_recording:
            self.get_logger().info('[Audio Server] Releasing Microphone (No active modules)...')
            self.is_recording = False
            if self.capture_thread:
                self.capture_thread.join()
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

    def capture_loop(self):
        while self.is_recording and rclpy.ok():
            try:
                if self.stream and self.stream.is_active():
                    data = self.stream.read(CHUNK, exception_on_overflow=False)
                    msg = UInt8MultiArray()
                    msg.data = list(data)
                    self.publisher.publish(msg)
            except Exception as e:
                self.get_logger().error(f'[Audio Server] Stream read error: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = BroneAudioNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.is_recording = False
        if node.capture_thread:
            node.capture_thread.join()
        if node.stream:
            node.stream.stop_stream()
            node.stream.close()
        node.pa.terminate()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
