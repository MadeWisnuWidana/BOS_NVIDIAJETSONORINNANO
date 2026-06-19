#!/bin/bash
# BRONE Jetson Manager Startup Script — BOS v3.1
source /opt/ros/humble/setup.bash
source ~/brone_vision_ws/install/setup.bash

export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/brone/cyclonedds.xml

# Jalankan Jetson Manager Node (Orkestrator utama)
/usr/bin/python3 /home/brone/brone_vision_ws/src/brone_perception/brone_perception/jetson_manager_node.py
