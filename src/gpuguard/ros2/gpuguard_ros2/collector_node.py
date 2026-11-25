"""GPU Collector ROS 2 node."""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from builtin_interfaces.msg import Time

from gpuguard_ros2.msg import GPUState
from gpuguard.collector.nvml_collector import NVMLCollector, MockNVMLCollector
from gpuguard.collector.sampler import GPUSampler
from gpuguard.utils.config import get_config, CollectorConfig
from gpuguard.utils.logging import get_logger, init_logging
from gpuguard.utils.time_utils import now_ns

logger = get_logger("ros2.collector_node")


class GPUCollectorNode(Node):
    """ROS 2 node that publishes GPU state from NVML."""

    def __init__(self, config: CollectorConfig = None, use_mock: bool = False):
        super().__init__('gpuguard_collector')

        self.config = config or get_config().collector
        self.use_mock = use_mock

        # QoS for GPU state (best effort, high frequency)
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # Publishers
        self._gpu_publishers: dict[int, rclpy.publisher.Publisher] = {}
        for gpu_id in self.config.gpu_indices:
            topic = f'/gpuguard/gpu_{gpu_id}/state'
            self._gpu_publishers[gpu_id] = self.create_publisher(GPUState, topic, qos)

        # Create collector
        if self.use_mock:
            self.collector = MockNVMLCollector(self.config)
        else:
            self.collector = NVMLCollector(self.config)

        # Create sampler
        self.sampler = GPUSampler(buffer_size=self.config.buffer_size)

        # Register callback
        self.collector.register_callback(self._on_gpu_state)

        # Timer for publishing
        self._timer = self.create_timer(
            self.config.poll_interval_ms / 1000.0,
            self._publish_loop,
        )

        # Initialize
        if not self.collector.initialize():
            self.get_logger().error("Failed to initialize NVML collector")

        # Cache GPU infos
        for gpu_id, info in self.collector.get_all_gpu_infos().items():
            self.sampler.set_gpu_info(gpu_id, info)

        self.get_logger().info(f"GPU Collector Node started, monitoring GPUs: {self.config.gpu_indices}")

    def _on_gpu_state(self, state) -> None:
        """Handle new GPU state from collector."""
        self.sampler.add_sample(state)

    def _publish_loop(self) -> None:
        """Publish latest GPU states."""
        for gpu_id, publisher in self._gpu_publishers.items():
            state = self.sampler.get_latest(gpu_id)
            if state:
                self._publish_gpu_state(publisher, state)

    def _publish_gpu_state(self, publisher, state) -> None:
        """Convert and publish GPU state."""
        msg = GPUState()
        msg.stamp = self._ns_to_time(state.timestamp_ns)
        msg.gpu_id = state.gpu_id
        msg.name = state.name
        msg.driver_version = state.driver_version

        msg.memory_used = state.memory_used
        msg.memory_total = state.memory_total
        msg.memory_free = state.memory_free
        msg.memory_used_pct = state.memory_used_pct

        msg.utilization_gpu = state.utilization_gpu
        msg.utilization_memory = state.utilization_memory

        msg.temperature_gpu = state.temperature_gpu
        msg.temperature_memory = state.temperature_memory

        msg.power_draw = state.power_draw
        msg.power_limit = state.power_limit
        msg.power_draw_pct = state.power_draw_pct

        msg.clock_graphics = state.clock_graphics
        msg.clock_sm = state.clock_sm
        msg.clock_mem = state.clock_mem
        msg.clock_video = state.clock_video

        msg.fan_speed = state.fan_speed
        msg.performance_state = state.performance_state
        msg.compute_mode = state.compute_mode

        msg.ecc_errors_volatile = state.ecc_errors_volatile
        msg.ecc_errors_aggregate = state.ecc_errors_aggregate

        msg.pcie_throughput_tx = state.pcie_throughput_tx
        msg.pcie_throughput_rx = state.pcie_throughput_rx
        msg.pcie_replay_counter = state.pcie_replay_counter

        msg.is_throttling = state.is_throttling
        msg.vram_pressure = state.vram_pressure

        publisher.publish(msg)

    def _ns_to_time(self, ns: int) -> Time:
        """Convert nanoseconds to ROS Time."""
        return Time(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)

    def destroy_node(self):
        """Clean shutdown."""
        self.collector.shutdown()
        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    # Parse args for mock mode
    import sys
    use_mock = '--mock' in sys.argv

    # Load config
    init_logging()

    node = GPUCollectorNode(use_mock=use_mock)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()