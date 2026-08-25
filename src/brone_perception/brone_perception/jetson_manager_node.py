import fcntl
import sys

try:
    _pid_file_jm = open("/tmp/jetson_manager_node.pid", "w")
    fcntl.flock(_pid_file_jm, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("⚠️ Another instance of jetson_manager_node.py is already running! Exiting duplicate process.")
    sys.exit(0)

#!/usr/bin/env python3
"""
=============================================================================
  BRONE Jetson Manager Node — BOS Vision 3.0
=============================================================================
  Mendengarkan perintah dari NUC via DDS, mengorkestrasi proses lokal
  (FER v2, Voice, Display), dan menggerakkan servo leher via ROS 2.

  CHANGELOG v3.1 (Alignment):
  [FIX #1] Path SST_TTS_DIR & REALTIME_DIR disesuaikan dengan struktur
           brone_vision_ws yang baru (brone_voice/brone_voice/...).
  [FIX #2] Prioritas sumber gaze: robot/fer_gaze HANYA aktif saat mode
           'eyefollow' atau 'fer'. Saat mode lain, perintah gaze diabaikan.
  [FIX #3] FER Publisher v2 digunakan (bukan lib/fer/publisher.py lama).
  [FIX #4] Command 'start_fer' dialihkan ke fer_v2/publisher.py dengan venv.
  [FIX #5] Subscribe robot/mode untuk tracking active_mode di manager.
=============================================================================
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import JointState
import subprocess
import json
import paho.mqtt.client as mqtt
import os
import time
import math
import psutil

_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# [FIX #1] Path disesuaikan dengan struktur folder yang benar
DISPLAY_DIR  = os.path.join(_PKG_DIR, "display_v2")
SST_TTS_DIR  = "/home/brone/brone_vision_ws/src/brone_voice/brone_voice/brone-sst-tts"
REALTIME_DIR = "/home/brone/brone_vision_ws/src/brone_voice/brone_voice/brone-voice-realtime"
# [FIX #3] Gunakan FER v2
FER_V2_DIR   = "/home/brone/brone_vision_ws/src/brone_perception/fer_v2"
FER_V2_VENV  = os.path.join(FER_V2_DIR, "venv", "bin", "python3")


class JetsonManagerNode(Node):
    def __init__(self):
        super().__init__('jetson_manager_node')

        # [FIX #5] Track active mode untuk prioritas gaze
        self.active_mode = "default"

        self.cmd_sub  = self.create_subscription(String, '/brone/jetson_cmd', self.listener_callback, 10)
        self.head_pub = self.create_publisher(JointState, '/robotis/head_control/set_joint_states', 10)
        self.ctrl_pub = self.create_publisher(String, '/brone/module_control', 10)

        self.get_logger().info('[JETSON MANAGER] BOS Vision 3.1 Manager Aktif.')

        self.display_process = None
        self.voice_process   = None
        self.fer_process     = None
        self.camera_process  = None
        self.gaze_process    = None
        self.voice_mode      = None

        self.current_pan  = 0.0
        self.current_tilt = 0.0

        self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_message = self._on_mqtt_message
        try:
            self.mqtt_client.connect('localhost', 1883, 60)
            self.mqtt_client.subscribe('robot/head_control')
            self.mqtt_client.subscribe('robot/fer_gaze')
            # [FIX #5] Subscribe mode untuk tracking active_mode
            self.mqtt_client.subscribe('robot/mode')
            self.mqtt_client.loop_start()
        except Exception as e:
            self.get_logger().error(f'Gagal connect MQTT: {e}')

        self.create_timer(5.0, self._monitor_processes)

    def _clamp(self, val, min_val, max_val):
        return max(min_val, min(val, max_val))

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            data  = json.loads(msg.payload.decode())

            # [FIX #5] Track active_mode dari MQTT robot/mode
            if topic == 'robot/mode':
                new_mode = data.get('mode', 'default')
                self.active_mode = new_mode
                self.get_logger().info(f'[MODE] Active display mode: {new_mode}')
                return

            pan, tilt = 0.0, 0.0

            if topic == 'robot/head_control':
                # robot/head_control dari Display V2 (browser JS)
                pan  = data.get('pan_deg', 0.0)
                tilt = data.get('tilt_deg', 0.0)

            elif topic == 'robot/fer_gaze':
                # [FIX #2] robot/fer_gaze dari FER v2 Python
                # HANYA aktif saat mode eyefollow atau fer
                if self.active_mode not in ('eyefollow', 'fer', 'mirror'):
                    return

                detected = data.get('face_detected', False)
                if not detected:
                    return

                gaze_x = data.get('gaze_x', 0.0)
                gaze_y = data.get('gaze_y', 0.0)
                pan    = gaze_x * -35.0
                tilt   = gaze_y * 20.0

            target_pan  = self._clamp(pan,  -45.0, 45.0)
            target_tilt = self._clamp(tilt, -30.0, 30.0)

            # EMA smoothing — responsif tapi tidak bergetar
            alpha = 0.12
            self.current_pan  = self.current_pan  + alpha * (target_pan  - self.current_pan)
            self.current_tilt = self.current_tilt + alpha * (target_tilt - self.current_tilt)

            js = JointState()
            js.name     = ['head_pan', 'head_tilt']
            js.position = [math.radians(self.current_pan), math.radians(self.current_tilt)]
            self.head_pub.publish(js)

        except Exception as e:
            self.get_logger().warn(f'[MQTT] Error: {e}')

    def listener_callback(self, msg):
        try:
            raw_data = msg.data
            command  = "".join([c for c in raw_data if c.isprintable()]).strip().lower()
            self.get_logger().info(f'[CMD] Diterima: "{command}"')
        except Exception:
            return

        # Web Display
        if command == 'start_display':
            self._start_display()

        # FER (Vision) — [FIX #3][FIX #4] Gunakan FER v2
        elif command in ['start_fer', 'fer']:
            self._start_fer()
        elif command in ['start_gaze', 'eyefollow']:
            self._start_gaze()
        elif command == 'stop_fer':
            self._stop_fer()

        # Civitas
        elif command == 'start_civitas':
            self._control_module('civitas', 'start')
        elif command == 'stop_civitas':
            self._control_module('civitas', 'stop')

        # Voice
        elif command in ['start_voice', 'talk']:
            self._start_voice("SST_TTS")
        elif command == 'start_realtime':
            self._start_voice("REALTIME")
        elif command == 'stop_voice':
            self._stop_voice()

        elif command in ['stop_all', 'stop']:
            self._stop_all()

    def _control_module(self, module, state):
        msg = String()
        msg.data = json.dumps({"module": module, "state": state})
        self.ctrl_pub.publish(msg)
        self.get_logger().info(f'[CTRL] Sent module {module} -> {state}')

    def _monitor_processes(self):
        if self.display_process and self.display_process.poll() is not None:
            self.get_logger().error('[HEARTBEAT] HTTP Server crash! Restarting...')
            self.display_process = None
            self._start_display()

        if self.voice_process and self.voice_process.poll() is not None:
            self.get_logger().error(f'[HEARTBEAT] Voice ({self.voice_mode}) crash! Restarting...')
            mode = self.voice_mode
            self.voice_process = None
            self._start_voice(mode)

    def _is_process_running(self, name_part):
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                if proc.info['cmdline'] and any(name_part in arg for arg in proc.info['cmdline']):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None

    def _start_display(self):
        if self.display_process and self.display_process.poll() is None:
            return
        if self._is_process_running("http.server"):
            return
        self.get_logger().info(f'[DISPLAY] Menjalankan HTTP Server dari: {DISPLAY_DIR}')
        self.display_process = subprocess.Popen(
            ["python3", "-m", "http.server", "8080"],
            cwd=DISPLAY_DIR
        )

    def _start_gaze(self):
        """Hanya jalankan Camera + Gaze. Tanpa FER v2."""
        # 1. Jalankan Camera Node
        if self.camera_process is None or self.camera_process.poll() is not None:
            self.get_logger().info('[GAZE] Menjalankan brone_camera_node...')
            self.camera_process = subprocess.Popen(
                ["ros2", "run", "brone_perception", "brone_camera_node"]
            )
        
        # 2. Jalankan Gaze Node
        if self.gaze_process is None or self.gaze_process.poll() is not None:
            self.get_logger().info('[GAZE] Menjalankan brone_gaze_node...')
            self.gaze_process = subprocess.Popen(
                ["ros2", "run", "brone_perception", "brone_gaze_node"]
            )
        
        self.get_logger().info('[GAZE] Camera + Gaze aktif. FER v2 TIDAK dijalankan.')

    def _start_fer(self):
        """Jalankan Camera, FER V2, dan Gaze sebagai node ROS 2."""
        # 1. Jalankan Camera Node
        if self.camera_process is None or self.camera_process.poll() is not None:
            self.get_logger().info('[VISION] Menjalankan brone_camera_node...')
            self.camera_process = subprocess.Popen(
                ["ros2", "run", "brone_perception", "brone_camera_node"]
            )
        
        # 2. Jalankan Gaze Node
        if self.gaze_process is None or self.gaze_process.poll() is not None:
            self.get_logger().info('[VISION] Menjalankan brone_gaze_node...')
            self.gaze_process = subprocess.Popen(
                ["ros2", "run", "brone_perception", "brone_gaze_node"]
            )

        # 3. Jalankan FER v2 (sekarang publisher_ros.py)
        if self.fer_process and self.fer_process.poll() is None:
            self.get_logger().info('[FER] FER v2 sudah berjalan, skip.')
            return

        self.get_logger().info('[FER] Menjalankan FER Publisher V2 (ROS)...')
        python_bin = FER_V2_VENV if os.path.exists(FER_V2_VENV) else "python3"
        try:
            self.fer_process = subprocess.Popen(
                [python_bin, "publisher_ros.py"],
                cwd=FER_V2_DIR
            )
        except Exception as e:
            self.get_logger().error(f'[FER] Gagal menjalankan FER v2: {e}')

    def _stop_fer(self):
        self.get_logger().info('[VISION] Mematikan Vision Nodes (FER, Gaze, Camera)...')
        for proc in [self.fer_process, self.gaze_process, self.camera_process]:
            if proc:
                import signal
                proc.send_signal(signal.SIGINT) # Graceful exit ROS 2
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self.fer_process = None
        self.gaze_process = None
        self.camera_process = None

    def _start_voice(self, mode):
        if self.voice_process and self.voice_process.poll() is None:
            if self.voice_mode == mode:
                return
            self._stop_voice()

        self.get_logger().info(f'[VOICE] Menjalankan {mode}...')
        try:
            if mode == "SST_TTS":
                # [FIX #1] Gunakan venv python dari brone-sst-tts
                venv_python = os.path.join(SST_TTS_DIR, "venv", "bin", "python3")
                python_bin  = venv_python if os.path.exists(venv_python) else "python3"
                env = os.environ.copy()
                env["XDG_RUNTIME_DIR"] = "/run/user/1000"
                env["PULSE_SERVER"] = "unix:/run/user/1000/pulse/native"
                self.voice_process = subprocess.Popen(
                    [python_bin, "main.py"],
                    cwd=SST_TTS_DIR,
                    env=env
                )
            else:
                self.voice_process = subprocess.Popen(
                    ["python3", "main.py"],
                    cwd=REALTIME_DIR
                )
            self.voice_mode = mode
        except Exception as e:
            self.get_logger().error(f"Gagal menjalankan voice: {e}")

    def _stop_voice(self):
        if self.voice_process:
            self.get_logger().info('[VOICE] Mematikan voice engine...')
            self.voice_process.terminate()
            try:
                self.voice_process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.voice_process.kill()
            self.voice_process = None
            self.voice_mode    = None

    def _stop_all(self):
        self.get_logger().info('[ALL] Menghentikan semua program Jetson...')
        self._stop_fer()
        self._stop_voice()
        self._control_module('civitas', 'stop')
        self._control_module('vad', 'stop')
        if self.display_process:
            self.display_process.terminate()
            self.display_process = None
        # Reset leher ke tengah
        self.current_pan  = 0.0
        self.current_tilt = 0.0
        js = JointState()
        js.name     = ['head_pan', 'head_tilt']
        js.position = [0.0, 0.0]
        self.head_pub.publish(js)


def main(args=None):
    rclpy.init(args=args)
    node = JetsonManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._stop_all()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
