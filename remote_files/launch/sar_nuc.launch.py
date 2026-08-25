import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Load Launch File bawaan OP3 Manager
    op3_manager_dir = get_package_share_directory('op3_manager')
    op3_manager_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(op3_manager_dir, 'launch', 'op3_manager.launch.py')
        )
    )

    # 2. Driver Kamera Webcam C920
    camera_node = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='v4l2_camera',
        parameters=[{
            'video_device': '/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_9DE4F4DF-video-index0',
            'image_size': [640, 480]
        }],
        output='screen'
    )

    # 3. Otak Lokalisasi Anda
    localization_node = Node(
        package='Lokalisasi',
        executable='Lokalisasi_SAR',
        name='improved_op3_localization',
        output='screen'
    )

    return LaunchDescription([
        op3_manager_launch,
        camera_node,
        localization_node
    ])
