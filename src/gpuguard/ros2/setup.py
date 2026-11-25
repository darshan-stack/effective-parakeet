from setuptools import find_packages, setup

package_name = 'gpuguard_ros2'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Darshan',
    maintainer_email='darshan@example.com',
    description='GPUGuard ROS 2 integration nodes',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'gpuguard_collector = gpuguard_ros2.collector_node:main',
            'gpuguard_monitor = gpuguard_ros2.monitor_node:main',
            'gpuguard_correlator = gpuguard_ros2.correlator_node:main',
            'gpuguard_anomaly = gpuguard_ros2.anomaly_node:main',
        ],
    },
)