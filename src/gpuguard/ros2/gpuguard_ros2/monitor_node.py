"""ROS 2 Monitor ROS 2 node."""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from rclpy.callback_groups import ReentrantCallbackGroup
from builtin_interfaces.msg import Time

from gpuguard_ros2.msg import TopicStats
from gpuguard.monitor.ros_monitor import create_ros_monitor
from gpuguard.monitor.topic_tracker import TopicTracker, TopicSample
from gpuguard.utils.config import get_config, MonitorConfig, ROS2Config
from gpuguard.utils.logging import get_logger, init_logging
from gpuguard.utils.time_utils import now_ns

logger = get_logger("ros2.monitor_node")


class ROSMonitorNode(Node):
    """ROS 2 node that monitors topic rates and latencies."""

    def __init__(self, config: MonitorConfig = None, ros_config: ROS2Config = None):
        super().__init__('gpuguard_monitor')

        self.config = config or get_config().monitor
        self.ros_config = ros_config or get_config().ros2

        # Create monitor
        self.monitor = create_ros_monitor(self.config, self.ros_config)

        # QoS for topic stats (reliable, lower frequency)
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # Publisher for topic stats
        self._stats_publisher = self.create_publisher(TopicStats, '/gpuguard/topic_stats', qos)

        # Timer for publishing stats
        self._timer = self.create_timer(1.0, self._publish_stats)

        # Start monitoring
        self.monitor.start_monitoring()

        # Register callback for real-time updates
        self.monitor.register_external_callback(self._on_topic_sample)

        self.get_logger().info(f"ROS Monitor Node started, monitoring: {self.config.topics}")

    def _on_topic_sample(self, topic: str, sample: TopicSample) -> None:
        """Handle new topic sample."""
        # Could publish individual samples here if needed
        pass

    def _publish_stats(self) -> None:
        """Publish topic statistics."""
        stats = self.monitor.get_all_stats()

        for topic, data in stats.items():
            msg = TopicStats()
            msg.stamp = self._ns_to_time(int(time.time() * 1e9))
            msg.topic = data['topic']
            msg.message_type = data['message_type']
            msg.sample_count = data['sample_count']

            msg.current_hz = data['current_hz']
            msg.avg_hz = data['avg_hz']
            msg.min_hz = data['min_hz'] if data['min_hz'] != float('inf') else 0.0
            msg.max_hz = data['max_hz']

            msg.avg_latency_ms = data['avg_latency_ms']
            msg.min_latency_ms = data['min_latency_ms']
            msg.max_latency_ms = data['max_latency_ms']
            msg.p50_latency_ms = data['p50_latency_ms']
            msg.p90_latency_ms = data['p90_latency_ms']
            msg.p95_latency_ms = data['p95_latency_ms']
            msg.p99_latency_ms = data['p99_latency_ms']

            msg.deadline_ms = data['deadline_ms']
            msg.deadline_misses = data['deadline_misses']
            msg.consecutive_misses = data['consecutive_misses']

            msg.avg_size_bytes = data['avg_size_bytes']
            msg.max_size_bytes = data['max_size_bytes']

            self._stats_publisher.publish(msg)

    def _ns_to_time(self, ns: int) -> Time:
        """Convert nanoseconds to ROS Time."""
        return Time(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)

    def destroy_node(self):
        """Clean shutdown."""
        self.monitor.shutdown()
        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    init_logging()

    node = ROSMonitorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()