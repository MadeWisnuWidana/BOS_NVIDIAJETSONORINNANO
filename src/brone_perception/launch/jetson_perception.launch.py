from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('enable_civitas', default_value='false'),
        
        Node(
            package='brone_perception',
            executable='jetson_manager',
            name='jetson_manager_node',
            output='screen',
        ),
        
        # We can add more nodes here conditionally later if needed
    ])
