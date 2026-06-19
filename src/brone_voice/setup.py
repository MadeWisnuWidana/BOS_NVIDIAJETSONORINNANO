from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'brone_voice'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'),
            glob('config/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='BRONE Team',
    maintainer_email='brone@ub.ac.id',
    description='BRONE Voice Engine — SST, TTS, and Realtime Voice Agent',
    license='MIT',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
        ],
    },
)
