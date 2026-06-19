from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='brone_perception',
            executable='jetson_manager',
            name='jetson_manager_node',
            output='screen',
        ),
        Node(
            package='brone_voice',
            executable='voice_node',
            name='voice_engine_node',
            output='screen',
        ),
        Node(
            package='brone_perception',
            executable='civitas_node',
            name='civitas_perception_node',
            output='screen',
        ),
    ])
