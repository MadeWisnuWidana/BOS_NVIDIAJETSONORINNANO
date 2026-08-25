#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# jalan.sh — OP3 Walking Launcher (FIXED: Menggunakan topic set_params)
# ══════════════════════════════════════════════════════════════════
# PERBAIKAN KRITIS:
#   Versi lama menggunakan "ros2 param set /op3_manager walking_param_*"
#   yang TIDAK PERNAH BEKERJA karena op3_manager tidak mendeklarasikan
#   parameter tersebut. Walking module OP3 menerima parameter melalui
#   topic /robotis/walking/set_params bertipe WalkingParam msg.
#
# PERBAIKAN CRABWALK & YAW DRIFT (16 Juli 2026 - Revisi 3):
#   Karena robot masih melenceng ke kanan dan harus diangkat manual,
#   kompensasi y_move_amplitude ditingkatkan menjadi -0.015 (1.5cm ke kiri).
#   Ditambahkan kompensasi setir angle_move_amplitude: 0.01 (belok kiri)
#   (diturunkan dari 0.02 karena pretes6 menunjukkan bablas ke kiri +41cm).
# ══════════════════════════════════════════════════════════════════

echo "🤖 [1/5] Mengambil alih kontrol ke Action Module..."
ros2 topic pub --once /robotis/enable_ctrl_module std_msgs/msg/String "{data: 'action_module'}"
sleep 1

echo "🧘 [2/5] Transisi perlahan ke postur Walk Ready..."
# Mengirim sinyal Action Page 9 (Walk Ready untuk OP3)
ros2 topic pub --once /robotis/action/page_num std_msgs/msg/Int32 "{data: 9}"
sleep 3  # Memberi waktu 3 detik agar robot bergerak perlahan dan stabil

echo "⚙️ [3/5] Menyerahkan otoritas ke Walking Module..."
ros2 topic pub --once /robotis/enable_ctrl_module std_msgs/msg/String "{data: 'walking_module'}"
sleep 1

echo "🔧 [4/5] Menyuntikkan Parameter Berjalan Ultra-Stable untuk Rumput Sintetis..."
# ──────────────────────────────────────────────────────────────────
# Konfigurasi Aktif: Baseline Bersih + Koreksi Crabwalk — 16 Juli 2026
# Berdasarkan analisis Uji_Walking30: robot drift ke kanan ~0.44° (0.8cm/m).
# Perubahan dari baseline:
#   - init_y_offset: 0.070 (tetap lebar untuk cegah leg clash di rumput sintetis)
#   - y_move_amplitude: -0.015 (Kompensasi crabwalk ke kanan — 1.5cm ke kiri)
#   - angle_move_amplitude: 0.01 (Kompensasi rotasi yaw — setir belok kiri konstan)
# offset.yaml: semua joint tetap 0 (bersih)
# ──────────────────────────────────────────────────────────────────
ros2 topic pub --once /robotis/walking/set_params op3_walking_module_msgs/msg/WalkingParam "{
  init_x_offset: -0.020,
  init_y_offset: 0.070,
  init_z_offset: 0.035,
  init_roll_offset: 0.0,
  init_pitch_offset: 0.0,
  init_yaw_offset: 0.0,
  period_time: 0.600,
  dsp_ratio: 0.20,
  step_fb_ratio: 0.28,
  x_move_amplitude: 0.015,
  y_move_amplitude: -0.015,
  z_move_amplitude: 0.060,
  angle_move_amplitude: 0.01,
  move_aim_on: false,
  balance_enable: true,
  balance_hip_roll_gain: 0.35,
  balance_knee_gain: 0.3,
  balance_ankle_roll_gain: 0.7,
  balance_ankle_pitch_gain: 0.9,
  y_swap_amplitude: 0.028,
  z_swap_amplitude: 0.006,
  arm_swing_gain: 0.2,
  pelvis_offset: 0.0,
  hip_pitch_offset: 0.0872665,
  p_gain: 0,
  i_gain: 0,
  d_gain: 0
}"
sleep 1

echo "🚀 [5/5] MEMULAI BERJALAN!"
ros2 topic pub --once /robotis/walking/command std_msgs/msg/String "{data: 'start'}"
