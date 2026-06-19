# BRONE Perception (Visual Cortex)

This package contains the perception and local control nodes for the BRONE Jetson Orin Nano system. It communicates with the Intel NUC `brone_core` via ROS 2 DDS topics and locally via MQTT.

## Architecture

- **ROS 2 Topic Bridge**: Listens to `/brone/jetson_cmd` to start/stop subsystems.
- **MQTT Broker**: Used for internal Jetson communication (FER ↔ Display).
- **Subsystems**:
  - `brone-display` (Web UI for robot face)
  - `FER-V2` (Facial Emotion Recognition)
  - `CivitasDetection` (UB uniform detection)
  - `brone-sst-tts` (Voice engine)

## Build Instructions

```bash
cd ~/brone_vision_ws
colcon build --packages-select brone_perception
source install/setup.bash
```

## Running the Manager

```bash
ros2 launch brone_perception jetson_perception.launch.py
```

## Structure

- `brone_perception/` — ROS 2 Nodes
- `lib/` — Reusable Python modules (FER, Civitas)
- `display/` — Web UI assets
- `config/` — Configuration files
- `models/` — ONNX models for inference
