from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'brone_perception'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Launch files
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
        # Config files
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml') + glob('config/*.conf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='BRONE Team',
    maintainer_email='brone@ub.ac.id',
    description='BRONE Visual Cortex — AI perception for Jetson Orin Nano',
    license='MIT',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'jetson_manager = brone_perception.jetson_manager_node:main',
            'brone_camera_node = brone_perception.brone_camera_node:main',
            'brone_audio_node = brone_perception.brone_audio_node:main',
            'fer_node = brone_perception.fer_node:main',
            'brone_vad_node = brone_perception.brone_vad:main',
            'civitas_node = brone_perception.civitas_node:main',
            'expression_arbitrator = brone_perception.expression_arbitrator:main',
            'brone_gaze_node = brone_perception.brone_gaze_node:main',
        ],
    },
)
