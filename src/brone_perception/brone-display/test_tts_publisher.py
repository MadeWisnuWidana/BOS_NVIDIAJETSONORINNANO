#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          BRONE — Dummy TTS / Expression Publisher            ║
║  Kirim ekspresi ke robot display via MQTT dari terminal.     ║
╠══════════════════════════════════════════════════════════════╣
║  Jalankan:  python test_tts_publisher.py                     ║
║  Pastikan Mosquitto sudah berjalan (port 1883).              ║
╚══════════════════════════════════════════════════════════════╝

Kegunaan:
  - Simulasi TTS speaking (robot mulut bergerak selama N detik)
  - Simulasi FER emotion (seolah-olah dikirim dari FER publisher)
  - Testing integrasi MQTT → browser display

Contoh:
  speak 3          → speaking animation 3 detik
  fer happy        → kirim emosi Happy ke topic fer_emotion
  mode mirror      → switch ke Mirror mode
  idle             → kembali ke idle
"""

import json
import time
import sys

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("❌ paho-mqtt belum terinstall.")
    print("   Jalankan: pip install paho-mqtt")
    sys.exit(1)


# ─── Configuration ───────────────────────────────────────────
MQTT_HOST = "localhost"
MQTT_PORT = 1883

TOPIC_EXPRESSION  = "robot/expression"      # TTS speaking commands
TOPIC_FER_EMOTION = "robot/fer_emotion"      # FER emotion data
TOPIC_MODE        = "robot/mode"             # Mode switching

# Mapping for convenience shortcuts
EMOTION_TO_EXPRESSION = {
    "happy":    "happier",
    "neutral":  "idle",
    "sad":      "sad",
    "shocked":  "shock",
    "upset":    "cry",
}

VALID_EXPRESSIONS = ["idle", "happy", "sad", "shock", "cry", "shy", "happier", "speaking"]
VALID_MODES = ["default", "mirror", "conversation"]


# ─── MQTT Setup ──────────────────────────────────────────────
def connect_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        time.sleep(0.3)
        print(f"✅ MQTT connected ({MQTT_HOST}:{MQTT_PORT})")
        return client
    except Exception as e:
        print(f"❌ MQTT connection failed: {e}")
        print("   Pastikan Mosquitto sudah jalan: sudo systemctl start mosquitto")
        sys.exit(1)


# ─── Command Handlers ────────────────────────────────────────
def cmd_speak(client, duration_str):
    """Send speaking animation command"""
    try:
        duration = float(duration_str)
    except ValueError:
        print("  ⚠️  Gunakan: speak <detik>  (contoh: speak 3)")
        return

    payload = {
        "expression": "speaking",
        "duration": duration
    }
    client.publish(TOPIC_EXPRESSION, json.dumps(payload))
    print(f"  → {TOPIC_EXPRESSION}: speaking {duration}s")


def cmd_fer(client, emotion_str):
    """Simulate FER emotion detection"""
    emotion = emotion_str.capitalize()

    expression = EMOTION_TO_EXPRESSION.get(emotion_str.lower())
    if not expression:
        print(f"  ⚠️  Emosi tidak dikenal: {emotion_str}")
        print(f"      Valid: {', '.join(EMOTION_TO_EXPRESSION.keys())}")
        return

    payload = {
        "timestamp": time.time(),
        "emotion": emotion,
        "expression": expression,
        "confidence": 0.92
    }
    client.publish(TOPIC_FER_EMOTION, json.dumps(payload))
    print(f"  → {TOPIC_FER_EMOTION}: {emotion} → {expression} (conf: 0.92)")


def cmd_expression(client, expr_str):
    """Send raw expression command"""
    if expr_str not in VALID_EXPRESSIONS:
        print(f"  ⚠️  Expression tidak valid: {expr_str}")
        print(f"      Valid: {', '.join(VALID_EXPRESSIONS)}")
        return

    payload = {"expression": expr_str, "duration": 0}
    client.publish(TOPIC_EXPRESSION, json.dumps(payload))
    print(f"  → {TOPIC_EXPRESSION}: {expr_str}")


def cmd_mode(client, mode_str):
    """Switch display mode"""
    if mode_str not in VALID_MODES:
        print(f"  ⚠️  Mode tidak valid: {mode_str}")
        print(f"      Valid: {', '.join(VALID_MODES)}")
        return

    payload = {"mode": mode_str, "timestamp_ms": int(time.time() * 1000)}
    client.publish(TOPIC_MODE, json.dumps(payload))
    print(f"  → {TOPIC_MODE}: {mode_str}")


def cmd_idle(client):
    """Quick shortcut: send idle"""
    payload = {"expression": "idle", "duration": 0}
    client.publish(TOPIC_EXPRESSION, json.dumps(payload))
    print(f"  → {TOPIC_EXPRESSION}: idle")


# ─── Help ─────────────────────────────────────────────────────
def show_help():
    print("""
  ╔══════════════════════════════════════════════════════════╗
  ║                    Available Commands                    ║
  ╠══════════════════════════════════════════════════════════╣
  ║  speak <detik>     Speaking animation (TTS simulasi)     ║
  ║  fer <emosi>       Simulasi FER emotion                  ║
  ║                    (happy/neutral/sad/shocked/upset)      ║
  ║  expr <state>      Raw expression command                ║
  ║                    (idle/happy/sad/shock/cry/shy/happier) ║
  ║  mode <mode>       Switch mode                           ║
  ║                    (default/mirror/conversation)          ║
  ║  idle              Shortcut: kembali ke idle             ║
  ║  help              Tampilkan bantuan ini                 ║
  ║  quit / exit       Keluar                                ║
  ╚══════════════════════════════════════════════════════════╝
""")


# ─── Main Interactive Loop ────────────────────────────────────
def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          BRONE — Dummy TTS / Expression Publisher        ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  Ketik 'help' untuk daftar perintah.                    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    client = connect_mqtt()
    show_help()

    try:
        while True:
            try:
                raw = input("  brone> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not raw:
                continue

            parts = raw.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "help":
                show_help()
            elif cmd == "speak":
                cmd_speak(client, arg or "3")
            elif cmd == "fer":
                if not arg:
                    print("  ⚠️  Gunakan: fer <emosi>  (contoh: fer happy)")
                else:
                    cmd_fer(client, arg)
            elif cmd == "expr":
                if not arg:
                    print("  ⚠️  Gunakan: expr <state>  (contoh: expr cry)")
                else:
                    cmd_expression(client, arg)
            elif cmd == "mode":
                if not arg:
                    print("  ⚠️  Gunakan: mode <mode>  (contoh: mode mirror)")
                else:
                    cmd_mode(client, arg)
            elif cmd == "idle":
                cmd_idle(client)
            else:
                # Try as raw expression shortcut
                if cmd in VALID_EXPRESSIONS:
                    cmd_expression(client, cmd)
                elif cmd in EMOTION_TO_EXPRESSION:
                    cmd_fer(client, cmd)
                else:
                    print(f"  ⚠️  Perintah tidak dikenal: {cmd}")
                    print("      Ketik 'help' untuk bantuan.")

    except KeyboardInterrupt:
        pass

    print("\n  👋 Bye!")
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
