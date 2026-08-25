#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# jalan_alvin.sh — Skenario B: VIO Konvensional/Baseline
# ══════════════════════════════════════════════════════════════════

echo "🚀 [1/3] Menjalankan VIO Baseline (Mas Alvin)..."
# Menjalankan Lokalisasi Alvin di background
python3 /home/brone/brone_vision_ws/remote_files/Lokalisasi_Alvin.py &
LOKALISASI_PID=$!
sleep 2

echo "📝 [2/3] Menjalankan Logger Compute.py..."
# Menjalankan logger di terminal ini (foreground) agar mudah di-stop dengan Ctrl+C
python3 /home/brone/brone_vision_ws/remote_files/Compute.py --prefix Skenario_B_Alvin --interval 0.1

# Trap Ctrl+C untuk mematikan background proses juga
trap "echo 'Mematikan VIO...'; kill $LOKALISASI_PID; exit" INT TERM
