import psutil
import time
import argparse
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from threading import Thread
import csv
import os

# Import ROS 2 Message Types
from sensor_msgs.msg import Imu
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_msgs.msg import String

class SuperLoggerNode(Node):
    def __init__(self, prefix, interval):
        super().__init__('super_logger_node')
        self.interval = interval
        
        # ---------------------------------------------------------
        # 1. SETUP PENYIMPANAN DATA (CSV)
        # ---------------------------------------------------------
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.filename = f"{prefix}_compute_imu_pose_{timestamp}.csv"
        
        # Membuat dan menyiapkan Header CSV
        self.csv_file = open(self.filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'Waktu_Elapsed(s)', 
            'CPU_Usage(%)', 
            'RAM_Usage(MB)', 
            'Acc_X_Mentah', 
            'Acc_X_Filter', 
            'Posisi_X_Hitung_Buruk', 
            'Posisi_X_Hitung_Baik',
            'Pose_X_Partikel', 
            'Pose_Y_Partikel',
            'Status_Robot',
            'Suhu_CPU(C)'
        ])

        # ---------------------------------------------------------
        # 2. VARIABEL GLOBAL UNTUK LOGGING
        # ---------------------------------------------------------
        self.start_time = time.time()
        
        # Variabel IMU & Hitung Manual
        self.raw_acc_x = 0.0
        self.filtered_acc_x = 0.0
        self.vel_x_buruk = 0.0
        self.pos_x_buruk = 0.0
        self.vel_x_baik = 0.0
        self.pos_x_baik = 0.0
        self.last_imu_time = None
        
        # Variabel Kalibrasi IMU
        self.calib_count = 0
        self.max_calib = 100
        self.bias_x = 0.0
        self.is_calibrated = False
        self.alpha = 0.15 # Low pass filter coeff
        
        # Variabel Pose (Particle Filter)
        self.pose_x_partikel = 0.0
        self.pose_y_partikel = 0.0
        self.status_robot = "Standby"

        # ---------------------------------------------------------
        # 3. SETUP SUBSCRIBERS (Mengambil Data dari Jaringan)
        # ---------------------------------------------------------
        self.get_logger().info("Menghubungkan ke Sensor IMU dan Partikel Filter...")
        
        self.sub_imu = self.create_subscription(
            Imu,
            '/robotis/open_cr/imu',
            self.imu_callback,
            10)
            
        self.sub_pose = self.create_subscription(
            PoseWithCovarianceStamped,
            '/op3/pose',  # Sesuaikan jika topik pose Anda berbeda
            self.pose_callback,
            10)

        self.sub_command = self.create_subscription(
            String,
            '/robotis/walking/command',
            self.command_callback,
            10)

        # ---------------------------------------------------------
        # 4. THREAD PENCATATAN UTAMA (Timer untuk menulis ke CSV)
        # ---------------------------------------------------------
        self.timer = self.create_timer(self.interval, self.log_data_callback)
        self.get_logger().info(f"Perekam Super Aktif! Interval: {self.interval}s. Sedang Kalibrasi IMU...")

    def imu_callback(self, msg):
        current_time = self.get_clock().now().nanoseconds / 1e9
        
        if self.last_imu_time is None:
            self.last_imu_time = current_time
            return
            
        dt = current_time - self.last_imu_time
        self.last_imu_time = current_time
        
        self.raw_acc_x = msg.linear_acceleration.x
        
        # Fase Kalibrasi IMU Statis
        if not self.is_calibrated:
            self.bias_x += self.raw_acc_x
            self.calib_count += 1
            if self.calib_count >= self.max_calib:
                self.bias_x /= self.max_calib
                self.is_calibrated = True
                self.get_logger().info(f"✅ Kalibrasi IMU Selesai! Bias X: {self.bias_x:.4f}")
            return

        # Hitungan Buruk (Tanpa Filter, Rawan Drift)
        self.vel_x_buruk += self.raw_acc_x * dt
        self.pos_x_buruk += self.vel_x_buruk * dt
        
        # Hitungan Baik (Low-Pass Filter + Clamping Kecepatan)
        acc_bersih = self.raw_acc_x - self.bias_x
        self.filtered_acc_x = self.alpha * acc_bersih + (1.0 - self.alpha) * self.filtered_acc_x
        
        self.vel_x_baik += self.filtered_acc_x * dt
        # Mencegah drift ekstrem (Clamping max kecepatan OP3 0.2 m/s)
        self.vel_x_baik = max(-0.20, min(0.20, self.vel_x_baik))
        
        self.pos_x_baik += self.vel_x_baik * dt

    def pose_callback(self, msg):
        # Menyimpan data estimasi posisi dari algoritma SLAM Canny Edge Anda
        self.pose_x_partikel = msg.pose.pose.position.x
        self.pose_y_partikel = msg.pose.pose.position.y

    def command_callback(self, msg):
        if msg.data == 'start':
            self.status_robot = 'Berjalan'
        elif msg.data == 'stop':
            self.status_robot = 'Berhenti'

    def log_data_callback(self):
        # Jangan merekam sebelum kalibrasi IMU selesai
        if not self.is_calibrated:
            return
            
        elapsed_time = time.time() - self.start_time
        
        # Menghitung Beban NUC
        cpu_usage = psutil.cpu_percent(interval=None)
        ram_info = psutil.virtual_memory()
        ram_usage_mb = ram_info.used / (1024 * 1024)
        
        # --- 4. THERMAL PROFILING ---
        suhu_cpu = 0.0
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                # Ambil sensor pertama yang tersedia (misal 'coretemp' di Intel NUC)
                for name, entries in temps.items():
                    if entries:
                        suhu_cpu = entries[0].current
                        break
        
        # Menulis Baris Baru ke CSV
        self.csv_writer.writerow([
            round(elapsed_time, 3),
            round(cpu_usage, 1),
            round(ram_usage_mb, 1),
            round(self.raw_acc_x, 4),
            round(self.filtered_acc_x, 4),
            round(self.pos_x_buruk, 4),
            round(self.pos_x_baik, 4),
            round(self.pose_x_partikel, 4),
            round(self.pose_y_partikel, 4),
            self.status_robot,
            round(suhu_cpu, 1)
        ])
        
        # Cetak info ringan ke terminal agar Anda tahu program berjalan
        print(f"[REC] {elapsed_time:.1f}s | CPU: {cpu_usage}% | Suhu: {suhu_cpu}C | Status: {self.status_robot}")

    def stop_logging(self):
        self.csv_file.close()
        print(f"\n✅ Data berhasil disimpan di: {os.path.abspath(self.filename)}")

def main():
    parser = argparse.ArgumentParser(description='Super Logger: Compute + IMU + Pose')
    parser.add_argument('--prefix', type=str, default='Eksperimen_Gabungan', help='Prefix untuk nama file CSV')
    parser.add_argument('--interval', type=float, default=0.1, help='Interval perekaman dalam detik (misal: 0.1 untuk 10 Hz)')
    args = parser.parse_args()

    rclpy.init()
    
    # Menggunakan MultiThreadedExecutor agar IMU, Pose, dan Timer bisa berjalan paralel
    node = SuperLoggerNode(args.prefix, args.interval)
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        print("\n🛑 Program dihentikan oleh user.")
    finally:
        node.stop_logging()
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
