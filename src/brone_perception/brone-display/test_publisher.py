#!/usr/bin/env python3
"""
Test Publisher - Sends sample expression data via MQTT
Use this to test the expression display system
"""

import paho.mqtt.client as mqtt
import json
import time
import argparse

def on_connect(client, userdata, flags, rc):
    """Callback when connected to MQTT broker"""
    if rc == 0:
        print("✓ Connected to MQTT broker")
    else:
        print(f"✗ Connection failed with code {rc}")

def on_publish(client, userdata, mid):
    """Callback when message is published"""
    print(f"✓ Message published (id: {mid})")

def send_expression(client, topic, expression, duration):
    """Send expression data to MQTT topic"""
    payload = {
        "expression": expression,
        "duration": duration
    }
    
    message = json.dumps(payload)
    result = client.publish(topic, message)
    
    print(f"→ Sending: {message}")
    return result

def main():
    parser = argparse.ArgumentParser(description='MQTT Expression Test Publisher')
    parser.add_argument('--host', default='localhost', help='MQTT broker host')
    parser.add_argument('--port', type=int, default=1883, help='MQTT broker port')
    parser.add_argument('--topic', default='robot/expression', help='MQTT topic')
    parser.add_argument('--expression', default='speaking', choices=['speaking', 'idle'], help='Expression type')
    parser.add_argument('--duration', type=float, default=5.0, help='Speaking duration in seconds')
    parser.add_argument('--loop', action='store_true', help='Run in loop mode (interactive)')
    
    args = parser.parse_args()
    
    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    print(f"Connecting to {args.host}:{args.port}...")
    
    try:
        client.connect(args.host, args.port, keepalive=60)
        client.loop_start()
        
        # Wait for connection
        time.sleep(1)
        
        if args.loop:
            # Interactive mode
            print("\n=== Interactive Mode ===")
            print("Commands:")
            print("  s <duration>  - Send speaking expression")
            print("  i             - Send idle expression")
            print("  q             - Quit")
            print("========================\n")
            
            while True:
                try:
                    user_input = input("Enter command: ").strip().lower()
                    
                    if user_input == 'q':
                        break
                    elif user_input == 'i':
                        send_expression(client, args.topic, 'idle', 0)
                    elif user_input.startswith('s'):
                        parts = user_input.split()
                        duration = float(parts[1]) if len(parts) > 1 else 3.0
                        send_expression(client, args.topic, 'speaking', duration)
                    else:
                        print("Unknown command. Use 's', 'i', or 'q'")
                        
                except KeyboardInterrupt:
                    break
                except ValueError as e:
                    print(f"Invalid input: {e}")
        else:
            # Single message mode
            send_expression(client, args.topic, args.expression, args.duration)
            time.sleep(1)  # Wait for message to be sent
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Disconnected")

if __name__ == '__main__':
    main()
