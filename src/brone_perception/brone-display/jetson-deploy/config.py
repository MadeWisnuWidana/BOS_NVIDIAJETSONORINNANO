"""
╔══════════════════════════════════════════════════════╗
║         BRONE SYSTEM — Jetson Configuration          ║
║  Edit paths here after cloning to your Jetson.       ║
╚══════════════════════════════════════════════════════╝

Struktur folder yang diharapkan di Jetson:
    ~/brone-system/
    ├── jetson-deploy/        ← folder ini (copy dari repo)
    │   ├── main-entry.py
    │   └── config.py         ← FILE INI
    ├── FER-BRONE/            ← clone dari github.com/FarrelPandhita/FER-BRONE
    │   └── publisher.py
    └── IntegrateSpeechExpression/  ← clone dari repo display
        └── index.html
"""

import os

# ─────────────────────────────────────────────────────────────
# BASE DIR  →  ganti sesuai lokasi folder brone-system di Jetson
# ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.expanduser("~/brone-system")

# ─────────────────────────────────────────────────────────────
# PATH MANUALS — sesuaikan jika struktur folder berbeda
# ─────────────────────────────────────────────────────────────
# FER-V2 publisher (pub.py di root FER-V2, atau app/publisher.py)
FER_PUBLISHER_PATH         = os.path.join(BASE_DIR, "FER-V2", "pub.py")
# Versi app/ (lebih lengkap, dengan haarcascade path handling)
FER_PUBLISHER_PATCHED_PATH = os.path.join(BASE_DIR, "FER-V2", "app", "publisher.py")
DISPLAY_SERVE_DIR          = os.path.join(BASE_DIR, "IntegrateSpeechExpression")

# ─────────────────────────────────────────────────────────────
# MQTT SETTINGS
# ─────────────────────────────────────────────────────────────
MQTT_HOST  = "localhost"
MQTT_PORT  = 1883          # Python native port
MQTT_PORT_WS = 9001        # WebSocket port (untuk browser)

# Topics — jangan diubah kecuali kamu juga ubah di app.js
TOPIC_MODE       = "robot/mode"
TOPIC_EXPRESSION = "robot/expression"
TOPIC_FER_EMOTION= "robot/fer_emotion"
TOPIC_FER_GAZE   = "robot/fer_gaze"

# ─────────────────────────────────────────────────────────────
# DISPLAY SERVER
# ─────────────────────────────────────────────────────────────
DISPLAY_PORT = 8080        # Port HTTP server untuk display web
DISPLAY_URL  = f"http://localhost:{DISPLAY_PORT}"

# ─────────────────────────────────────────────────────────────
# FER SETTINGS
# ─────────────────────────────────────────────────────────────
FER_CONFIDENCE_THRESHOLD = 0.50   # Sinkronkan dengan app.js
CAMERA_INDEX = 0                   # Index kamera utama di Jetson

# ─────────────────────────────────────────────────────────────
# Mode yang valid
# ─────────────────────────────────────────────────────────────
VALID_MODES = ["default", "mirror", "conversation"]
