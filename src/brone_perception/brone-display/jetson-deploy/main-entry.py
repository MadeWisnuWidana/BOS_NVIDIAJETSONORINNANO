#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║              BRONE SYSTEM — Main Entry CLI                   ║
║     Remote Control untuk BRONE Robot Expression Display      ║
╠══════════════════════════════════════════════════════════════╣
║  Jalankan: python3 main-entry.py                             ║
║  Pastikan Mosquitto sudah berjalan sebelum menjalankan ini.  ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import os
import json
import time
import subprocess
import threading

# ─── Import config lokal ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    MQTT_HOST, MQTT_PORT, TOPIC_MODE, TOPIC_EXPRESSION,
    FER_PUBLISHER_PATH, FER_PUBLISHER_PATCHED_PATH,
    DISPLAY_SERVE_DIR, DISPLAY_PORT,
    DISPLAY_URL, VALID_MODES
)

# ─── MQTT (paho) ────────────────────────────────────────────────
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[ERROR] paho-mqtt belum terinstall.")
    print("        Jalankan: pip3 install paho-mqtt")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════
#  SYSTEM STATE
# ════════════════════════════════════════════════════════════════
class BroneSystem:
    def __init__(self):
        self.current_mode    = "default"
        self.mqtt_connected  = False
        self.fer_process     = None   # subprocess FER publisher
        self.http_process    = None   # subprocess HTTP display server
        self.mqtt_client     = None
        self._mode_lock      = threading.Lock()

    # ── Properties ───────────────────────────────────────────────
    @property
    def fer_running(self):
        return self.fer_process is not None and self.fer_process.poll() is None

    @property
    def http_running(self):
        return self.http_process is not None and self.http_process.poll() is None

    # ── MQTT ─────────────────────────────────────────────────────
    def connect_mqtt(self):
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.mqtt_client.on_connect    = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            time.sleep(0.8)  # beri waktu koneksi
        except Exception as e:
            print(f"\n  [MQTT] Gagal konek: {e}")
            print(  "  [TIPS] Pastikan Mosquitto sudah jalan:")
            print(  "         sudo systemctl start mosquitto")
            return False
        return self.mqtt_connected

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        self.mqtt_connected = (rc == 0)

    def _on_mqtt_disconnect(self, client, userdata, rc, properties=None, reasonCode=None):
        self.mqtt_connected = False

    def publish_mode(self, mode: str):
        if not self.mqtt_connected:
            print("  [!] MQTT tidak terkoneksi — mode tidak terkirim ke display.")
            return
        payload = json.dumps({"mode": mode, "timestamp_ms": int(time.time() * 1000)})
        self.mqtt_client.publish(TOPIC_MODE, payload)

    def publish_expression(self, expression: str, duration: float = 0):
        if not self.mqtt_connected:
            return
        payload = json.dumps({"expression": expression, "duration": duration})
        self.mqtt_client.publish(TOPIC_EXPRESSION, payload)

    # ── Subprocess Management ─────────────────────────────────────
    def start_fer(self):
        if self.fer_running:
            return
        # Gunakan publisher_brone.py (versi patched) yang publish ke robot/fer_emotion
        fer_path = FER_PUBLISHER_PATCHED_PATH
        if not os.path.exists(fer_path):
            # Fallback ke publisher asli jika patched belum di-copy
            fer_path = FER_PUBLISHER_PATH
            if not os.path.exists(fer_path):
                print(f"\n  [!] FER publisher tidak ditemukan.")
                print(f"      Cek path di config.py:")
                print(f"        FER_PUBLISHER_PATCHED_PATH = {FER_PUBLISHER_PATCHED_PATH}")
                print(f"      Jalankan: cp jetson-deploy/publisher_brone.py FER-BRONE/")
                return
            print(f"  [!] publisher_brone.py tidak ada — menggunakan publisher.py asli")
            print(f"      (Fitur FER mungkin tidak berfungsi sempurna)")
        print("  → Menjalankan FER publisher...")
        self.fer_process = subprocess.Popen(
            [sys.executable, fer_path],
            cwd=os.path.dirname(fer_path)
        )
        time.sleep(1.5)
        print(f"  ✓ FER publisher berjalan (PID: {self.fer_process.pid})")

    def stop_fer(self):
        if not self.fer_running:
            return
        print("  → Menghentikan FER publisher...")
        self.fer_process.terminate()
        try:
            self.fer_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.fer_process.kill()
        self.fer_process = None
        print("  ✓ FER publisher dihentikan")

    def start_http_server(self):
        if self.http_running:
            return
        if not os.path.isdir(DISPLAY_SERVE_DIR):
            print(f"\n  [!] Folder display tidak ditemukan: {DISPLAY_SERVE_DIR}")
            print(  "      Sesuaikan DISPLAY_SERVE_DIR di config.py")
            return
        print(f"  → Menjalankan HTTP server di port {DISPLAY_PORT}...")
        self.http_process = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(DISPLAY_PORT)],
            cwd=DISPLAY_SERVE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(0.5)
        print(f"  ✓ Display tersedia di: {DISPLAY_URL}")

    def stop_http_server(self):
        if not self.http_running:
            return
        self.http_process.terminate()
        try:
            self.http_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.http_process.kill()
        self.http_process = None

    # ── Mode Switching ────────────────────────────────────────────
    def set_mode(self, mode: str):
        with self._mode_lock:
            if mode not in VALID_MODES:
                print(f"  [!] Mode tidak valid: {mode}")
                return

            prev = self.current_mode
            self.current_mode = mode

            if mode == "default":
                self.stop_fer()

            elif mode in ("mirror", "conversation"):
                self.start_fer()

            self.publish_mode(mode)
            print(f"\n  ✓ Mode: {prev} → {mode}")
            if mode == "mirror":
                print("    Robot akan meniru ekspresi wajah user secara real-time.")
            elif mode == "conversation":
                print("    Robot berbicara (TTS) + meniru emosi di sela-sela bicara.")
            elif mode == "default":
                print("    Robot dalam kondisi idle, gaze tracking aktif via browser.")

    def shutdown(self):
        print("\n  Shutdown — mematikan semua subsistem...")
        self.stop_fer()
        self.stop_http_server()
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        print("  ✓ Semua subsistem dihentikan. Sampai jumpa!\n")

    def status_string(self):
        mqtt_s = "✓ Connected" if self.mqtt_connected else "✗ Disconnected"
        fer_s  = f"✓ Running (PID {self.fer_process.pid})" if self.fer_running else "○ Off"
        http_s = f"✓ Running (port {DISPLAY_PORT})" if self.http_running else "○ Off"
        return (
            f"  MQTT Broker   : {mqtt_s}\n"
            f"  Mode Aktif    : {self.current_mode.upper()}\n"
            f"  FER Publisher : {fer_s}\n"
            f"  HTTP Server   : {http_s}\n"
            f"  Display URL   : {DISPLAY_URL}"
        )


# ════════════════════════════════════════════════════════════════
#  CLI DISPLAY HELPERS
# ════════════════════════════════════════════════════════════════
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
GREY   = "\033[90m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def banner(system: BroneSystem):
    mode = system.current_mode
    mode_color = {
        "default":      GREY,
        "mirror":       CYAN,
        "conversation": YELLOW,
    }.get(mode, GREY)

    print(f"{BOLD}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║       BRONE SYSTEM  —  Access Control CLI            ║{RESET}")
    print(f"{BOLD}╠══════════════════════════════════════════════════════╣{RESET}")
    print(f"{BOLD}║{RESET}  Status : {GREEN if system.mqtt_connected else RED}"
          f"{'● MQTT OK' if system.mqtt_connected else '● MQTT OFFLINE'}{RESET}")
    print(f"{BOLD}║{RESET}  Mode   : {mode_color}{BOLD}{mode.upper()}{RESET}")
    print(f"{BOLD}║{RESET}  FER    : "
          f"{'✓ Jalan' if system.fer_running else '○ Off'}")
    print(f"{BOLD}╚══════════════════════════════════════════════════════╝{RESET}")
    print()

def menu(system: BroneSystem):
    """Print menu utama dan return pilihan user."""
    banner(system)

    print(f"  {BOLD}Pilih fitur BRONE:{RESET}")
    print()

    active = system.current_mode
    def mark(m): return f"{GREEN}[AKTIF]{RESET} " if active == m else "        "

    print(f"  {mark('default')}1. Default Mode      — Idle face + gaze tracking")
    print(f"  {mark('mirror' )}2. Mirror Mode       — Robot meniru ekspresi user (FER)")
    print(f"  {mark('conversation')}3. Conversation Mode — TTS speaking + FER antara ucapan")
    print()
    print(f"  {'        '}4. Cek Status Sistem")
    print(f"  {'        '}5. Test Speaking (kirim animasi mulut 3 detik)")
    print()
    print(f"  {GREY}{'        '}0. Exit (stop semua){RESET}")
    print()

    try:
        choice = input(f"  {BOLD}Input >{RESET} ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "0"

    return choice


# ════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ════════════════════════════════════════════════════════════════
def main():
    system = BroneSystem()

    # ── 1. Startup ───────────────────────────────────────────────
    clear()
    print(f"\n{BOLD}  Memulai BRONE System...{RESET}\n")

    # Start HTTP server untuk display
    system.start_http_server()

    # Connect MQTT
    print("  → Menghubungkan ke MQTT broker...")
    if not system.connect_mqtt():
        print(f"\n  {RED}[!] Tidak bisa lanjut tanpa MQTT.{RESET}")
        print("      Jalankan Mosquitto dulu, lalu coba lagi.\n")
        sys.exit(1)
    print("  ✓ MQTT terhubung\n")

    time.sleep(0.5)

    # ── 2. Main interactive loop ──────────────────────────────────
    try:
        while True:
            clear()
            choice = menu(system)

            if choice == "1":
                system.set_mode("default")

            elif choice == "2":
                system.set_mode("mirror")

            elif choice == "3":
                system.set_mode("conversation")

            elif choice == "4":
                clear()
                print(f"\n{BOLD}  Status Sistem:{RESET}\n")
                print(system.status_string())
                print()
                input("  Tekan Enter untuk kembali...")

            elif choice == "5":
                system.publish_expression("speaking", 3.0)
                print("\n  ✓ Test speaking dikirim (3 detik).\n"
                      "  Pastikan display terbuka di browser.")
                time.sleep(1.5)

            elif choice == "0":
                break

            else:
                print(f"\n  {RED}Pilihan tidak valid.{RESET}")
                time.sleep(0.8)

    except KeyboardInterrupt:
        pass

    finally:
        system.shutdown()


if __name__ == "__main__":
    main()
