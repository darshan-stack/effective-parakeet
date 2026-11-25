"""GPUGuard ROS 2 launch file."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter
from launch_ros.substitutions import FindPackageShare


def launch_setup(context, *args, **kwargs):
    """Setup launch configuration."""

    # Get launch arguments
    use_mock = LaunchConfiguration('use_mock').perform(context).lower() == 'true'
    ros_domain_id = LaunchConfiguration('ros_domain_id').perform(context)
    config_file = LaunchConfiguration('config_file').perform(context)
    gpu_indices = LaunchConfiguration('gpu_indices').perform(context)
    poll_interval = LaunchConfiguration('poll_interval').perform(context)
    log_level = LaunchConfiguration('log_level').perform(context)

    # Parse GPU indices
    gpu_list = [int(x.strip()) for x in gpu_indices.split(',') if x.strip()]

    nodes = []

    # GPU Collector Node
    collector_node = Node(
        package='gpuguard_ros2',
        executable='gpuguard_collector',
        name='gpuguard_collector',
        output='screen',
        arguments=['--mock'] if use_mock else [],
        parameters=[{
            'gpu_indices': gpu_list,
            'poll_interval_ms': int(poll_interval),
            'config_file': config_file if config_file else '',
        }],
        ros_arguments=['--log-level', log_level],
    )
    nodes.append(collector_node)

    # ROS Monitor Node
    monitor_node = Node(
        package='gpuguard_ros2',
        executable='gpuguard_monitor',
        name='gpuguard_monitor',
        output='screen',
        parameters=[{
            'topics': [
                '/camera/detection',
                '/scan',
                '/odom',
                '/plan',
                '/cmd_vel',
                '/amcl_pose',
                '/tf',
            ],
            'deadline_ms': 50,
            'window_size': 100,
            'hz_window_s': 5.0,
        }],
        ros_arguments=['--log-level', log_level],
    )
    nodes.append(monitor_node)

    # Correlator Node
    correlator_node = Node(
        package='gpuguard_ros2',
        executable='gpuguard_correlator',
        name='gpuguard_correlator',
        output='screen',
        parameters=[{
            'sync_tolerance_ms': 5,
            'min_samples': 50,
            'granger_maxlag': 10,
            'rolling_window': 200,
        }],
        ros_arguments=['--log-level', log_level],
    )
    nodes.append(correlator_node)

    # Anomaly Detector Node
    anomaly_node = Node(
        package='gpuguard_ros2',
        executable='gpuguard_anomaly',
        name='gpuguard_anomaly_detector',
        output='screen',
        parameters=[{
            'vram_threshold_pct': 85.0,
            'temp_threshold_c': 80.0,
            'temp_critical_c': 85.0,
            'clock_drop_threshold_pct': 15.0,
            'power_throttle_threshold_pct': 90.0,
            'latency_spike_threshold': 3.0,
            'hz_drop_threshold_pct': 30.0,
            'deadline_miss_threshold': 3,
            'ecc_error_threshold': 0,
        }],
        ros_arguments=['--log-level', log_level],
    )
    nodes.append(anomaly_node)

    return nodes


def generate_launch_description():
    """Generate launch description."""
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'use_mock',
            default_value='false',
            description='Use mock GPU collector (no real GPU required)',
        ),
        DeclareLaunchArgument(
            'ros_domain_id',
            default_value='0',
            description='ROS_DOMAIN_ID',
        ),
        DeclareLaunchArgument(
            'config_file',
            default_value='',
            description='Path to GPUGuard config YAML file',
        ),
        DeclareLaunchArgument(
            'gpu_indices',
            default_value='0',
            description='Comma-separated GPU indices to monitor',
        ),
        DeclareLaunchArgument(
            'poll_interval',
            default_value='100',
            description='GPU polling interval in milliseconds',
        ),
        DeclareLaunchArgument(
            'log_level',
            default_value='info',
            description='Log level (debug, info, warn, error)',
        ),

        # Set ROS domain ID
        SetParameter(name='ros_domain_id', value=LaunchConfiguration('ros_domain_id')),

        # Opaque function to create nodes
        OpaqueFunction(function=launch_setup),
    ])