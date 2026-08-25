#!/bin/bash
echo "🛑 MENGHENTIKAN ROBOT..."
ros2 topic pub --once /robotis/walking/command std_msgs/msg/String "{data: 'stop'}"

