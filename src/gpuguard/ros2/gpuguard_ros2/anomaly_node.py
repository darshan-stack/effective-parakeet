"""Anomaly Detector ROS 2 node."""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from builtin_interfaces.msg import Time

from gpuguard_ros2.msg import Anomaly, GPUState, TopicStats
from gpuguard.utils.config import get_config, AnomalyConfig
from gpuguard.utils.logging import get_logger, init_logging
from gpuguard.utils.time_utils import now_ns

logger = get_logger("ros2.anomaly_node")


class AnomalyDetectorNode(Node):
    """ROS 2 node that detects anomalies in GPU and ROS metrics."""

    def __init__(self, config: AnomalyConfig = None):
        super().__init__('gpuguard_anomaly_detector')

        self.config = config or get_config().anomaly

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # Publishers
        self._anomaly_publisher = self.create_publisher(Anomaly, '/gpuguard/anomalies', qos)

        # State tracking
        self._gpu_states = {}
        self._topic_stats = {}
        self._anomaly_history = []

        # Subscribers (will be created dynamically)
        self._gpu_subs = {}
        self._topic_subs = {}

        # Timer for checking anomalies
        self._timer = self.create_timer(1.0, self._check_anomalies)

        self.get_logger().info("Anomaly Detector Node started")

    def _check_anomalies(self) -> None:
        """Check for anomalies in current state."""
        now = now_ns()

        # Check GPU anomalies
        for gpu_id, state in self._gpu_states.items():
            self._check_gpu_anomalies(gpu_id, state, now)

        # Check ROS anomalies
        for topic, stats in self._topic_stats.items():
            self._check_topic_anomalies(topic, stats, now)

    def _check_gpu_anomalies(self, gpu_id: int, state: GPUState, now: int) -> None:
        """Check GPU-specific anomalies."""
        # VRAM pressure
        if state.memory_used_pct >= self.config.vram_threshold_pct:
            self._publish_anomaly(
                type="vram",
                severity="warning" if state.memory_used_pct < 95 else "critical",
                gpu_metric="memory_used_pct",
                ros_topic="",
                message=f"GPU {gpu_id} VRAM usage at {state.memory_used_pct:.1f}%",
                value=state.memory_used_pct,
                threshold=self.config.vram_threshold_pct,
                now=now,
            )

        # Thermal throttling
        if state.temperature_gpu >= self.config.temp_critical_c:
            self._publish_anomaly(
                type="thermal",
                severity="critical",
                gpu_metric="temperature_gpu",
                ros_topic="",
                message=f"GPU {gpu_id} critical temperature: {state.temperature_gpu:.1f}°C",
                value=state.temperature_gpu,
                threshold=self.config.temp_critical_c,
                now=now,
            )
        elif state.temperature_gpu >= self.config.temp_threshold_c:
            self._publish_anomaly(
                type="thermal",
                severity="warning",
                gpu_metric="temperature_gpu",
                ros_topic="",
                message=f"GPU {gpu_id} high temperature: {state.temperature_gpu:.1f}°C",
                value=state.temperature_gpu,
                threshold=self.config.temp_threshold_c,
                now=now,
            )

        # Clock drop (throttling)
        if state.clock_graphics > 0:
            # We'd need baseline to detect drop - simplified check
            if state.is_throttling:
                self._publish_anomaly(
                    type="clock",
                    severity="warning",
                    gpu_metric="clock_graphics",
                    ros_topic="",
                    message=f"GPU {gpu_id} clock throttling detected",
                    value=float(state.clock_graphics),
                    threshold=0.0,
                    now=now,
                )

        # Power limit throttle
        if state.power_draw_pct >= self.config.power_throttle_threshold_pct:
            self._publish_anomaly(
                type="power",
                severity="warning",
                gpu_metric="power_draw_pct",
                ros_topic="",
                message=f"GPU {gpu_id} power limit throttle: {state.power_draw_pct:.1f}%",
                value=state.power_draw_pct,
                threshold=self.config.power_throttle_threshold_pct,
                now=now,
            )

        # ECC errors
        if state.ecc_errors_volatile > self.config.ecc_error_threshold:
            self._publish_anomaly(
                type="ecc",
                severity="critical",
                gpu_metric="ecc_errors_volatile",
                ros_topic="",
                message=f"GPU {gpu_id} ECC errors detected: {state.ecc_errors_volatile}",
                value=float(state.ecc_errors_volatile),
                threshold=float(self.config.ecc_error_threshold),
                now=now,
            )

    def _check_topic_anomalies(self, topic: str, stats: TopicStats, now: int) -> None:
        """Check ROS topic anomalies."""
        # Latency spike
        if stats.avg_latency_ms > 0 and stats.p99_latency_ms > stats.avg_latency_ms * self.config.latency_spike_threshold:
            self._publish_anomaly(
                type="latency",
                severity="warning",
                gpu_metric="",
                ros_topic=topic,
                message=f"Topic {topic} latency spike: P99={stats.p99_latency_ms:.1f}ms",
                value=stats.p99_latency_ms,
                threshold=stats.avg_latency_ms * self.config.latency_spike_threshold,
                now=now,
            )

        # Hz drop
        expected_hz = 1000.0 / stats.deadline_ms if stats.deadline_ms > 0 else 0
        if expected_hz > 0 and stats.current_hz < expected_hz * (1 - self.config.hz_drop_threshold_pct / 100):
            self._publish_anomaly(
                type="hz_drop",
                severity="warning",
                gpu_metric="",
                ros_topic=topic,
                message=f"Topic {topic} rate dropped: {stats.current_hz:.1f}Hz (expected {expected_hz:.1f}Hz)",
                value=stats.current_hz,
                threshold=expected_hz * (1 - self.config.hz_drop_threshold_pct / 100),
                now=now,
            )

        # Deadline misses
        if stats.consecutive_misses >= self.config.deadline_miss_threshold:
            self._publish_anomaly(
                type="deadline",
                severity="critical" if stats.consecutive_misses > 5 else "warning",
                gpu_metric="",
                ros_topic=topic,
                message=f"Topic {topic} missed {stats.consecutive_misses} consecutive deadlines",
                value=float(stats.consecutive_misses),
                threshold=float(self.config.deadline_miss_threshold),
                now=now,
            )

    def _publish_anomaly(self, type: str, severity: str, gpu_metric: str, ros_topic: str,
                         message: str, value: float, threshold: float, now: int) -> None:
        """Publish anomaly message."""
        msg = Anomaly()
        msg.stamp = self._ns_to_time(now)
        msg.type = type
        msg.severity = severity
        msg.gpu_metric = gpu_metric
        msg.ros_topic = ros_topic
        msg.message = message
        msg.value = value
        msg.threshold = threshold

        self._anomaly_publisher.publish(msg)

        # Log
        log_func = self.get_logger().error if severity == "critical" else self.get_logger().warn
        log_func(f"ANOMALY [{severity.upper()}] {message}")

        # Store in history
        self._anomaly_history.append({
            "timestamp": now,
            "type": type,
            "severity": severity,
            "gpu_metric": gpu_metric,
            "ros_topic": ros_topic,
            "message": message,
            "value": value,
            "threshold": threshold,
        })

        # Trim history
        if len(self._anomaly_history) > 1000:
            self._anomaly_history = self._anomaly_history[-1000:]

    def _ns_to_time(self, ns: int) -> Time:
        """Convert nanoseconds to ROS Time."""
        return Time(sec=ns // 1_000_000_000, nanosec=ns % 1_000_000_000)

    # Callbacks
    def _gpu_callback(self, msg: GPUState, gpu_id: int):
        """Handle GPU state message."""
        self._gpu_states[gpu_id] = msg

    def _topic_callback(self, msg: TopicStats):
        """Handle topic stats message."""
        self._topic_stats[msg.topic] = msg


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    init_logging()

    node = AnomalyDetectorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()