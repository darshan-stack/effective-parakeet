"""Correlator ROS 2 node."""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from builtin_interfaces.msg import Time

from gpuguard_ros2.msg import Correlation, GPUState, TopicStats
from gpuguard.correlation.correlator import Correlator, CorrelationResult
from gpuguard.correlation.time_sync import TimeSynchronizer
from gpuguard.utils.config import get_config, CorrelationConfig
from gpuguard.utils.logging import get_logger, init_logging
from gpuguard.utils.time_utils import now_ns

logger = get_logger("ros2.correlator_node")


class CorrelatorNode(Node):
    """ROS 2 node that computes GPU-ROS correlations."""

    def __init__(self, config: CorrelationConfig = None):
        super().__init__('gpuguard_correlator')

        self.config = config or get_config().correlation

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # Publishers
        self._corr_publisher = self.create_publisher(Correlation, '/gpuguard/correlations', qos)

        # Subscribers
        self._gpu_subs = {}
        self._topic_subs = {}

        # Correlator
        self.correlator = Correlator(self.config)

        # Timer for computing correlations
        self._timer = self.create_timer(2.0, self._compute_and_publish)

        # Track GPU IDs and topics
        self._gpu_ids = set()
        self._topics = set()

        self.get_logger().info("Correlator Node started")

    def _setup_subscriptions(self):
        """Setup dynamic subscriptions based on discovered topics."""
        # This would be called when new GPU/topic data arrives
        pass

    def _compute_and_publish(self) -> None:
        """Compute and publish correlations."""
        results = self.correlator.compute_correlations()

        for result in results:
            msg = Correlation()
            msg.stamp = self._ns_to_time(result.timestamp_ns)
            msg.gpu_metric = result.gpu_metric
            msg.ros_topic = result.ros_topic
            msg.correlation = result.correlation
            msg.p_value = result.p_value
            msg.lag_samples = result.lag_samples
            msg.lag_ms = result.lag_ms
            msg.method = result.method
            msg.sample_count = result.sample_count
            msg.significant = result.significant

            self._corr_publisher.publish(msg)

    def _ns_to_time(self, ns: int) -> Time:
        """Convert nanoseconds to ROS Time."""
        return Time(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)

    # Callback for GPU state
    def _gpu_callback(self, msg: GPUState, gpu_id: int):
        """Handle GPU state message."""
        self._gpu_ids.add(gpu_id)

        # Feed to correlator
        self.correlator.add_gpu_metric(f"gpu_{gpu_id}_utilization_gpu", msg.stamp.sec * 1e9 + msg.stamp.nanosec, msg.utilization_gpu)
        self.correlator.add_gpu_metric(f"gpu_{gpu_id}_memory_used_pct", msg.stamp.sec * 1e9 + msg.stamp.nanosec, msg.memory_used_pct)
        self.correlator.add_gpu_metric(f"gpu_{gpu_id}_temperature_gpu", msg.stamp.sec * 1e9 + msg.stamp.nanosec, msg.temperature_gpu)
        self.correlator.add_gpu_metric(f"gpu_{gpu_id}_power_draw", msg.stamp.sec * 1e9 + msg.stamp.nanosec, msg.power_draw)
        self.correlator.add_gpu_metric(f"gpu_{gpu_id}_clock_graphics", msg.stamp.sec * 1e9 + msg.stamp.nanosec, msg.clock_graphics)

    # Callback for topic stats
    def _topic_callback(self, msg: TopicStats):
        """Handle topic stats message."""
        self._topics.add(msg.topic)

        # Feed to correlator
        timestamp = msg.stamp.sec * 1e9 + msg.stamp.nanosec
        self.correlator.add_ros_metric(msg.topic, timestamp, msg.current_hz)
        self.correlator.add_ros_metric(f"{msg.topic}_latency", timestamp, msg.avg_latency_ms)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    init_logging()

    node = CorrelatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()