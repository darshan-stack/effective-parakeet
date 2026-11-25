"""ROS 2 monitoring node for GPUGuard."""
import threading
import time
from typing import Dict, List, Optional, Callable, Any
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from rclpy.subscription import Subscription
from rclpy.callback_groups import ReentrantCallbackGroup
from rosidl_runtime_py import get_message_interfaces
from rosidl_runtime_py.utilities import get_message

from gpuguard.monitor.topic_tracker import TopicTracker, TopicSample, LatencyAnalyzer
from gpuguard.utils.config import get_config, MonitorConfig, ROS2Config
from gpuguard.utils.logging import get_logger, LogContext
from gpuguard.utils.time_utils import now_ns

logger = get_logger("monitor.ros_monitor")


class ROSMonitorNode(Node):
    """ROS 2 node that monitors topic rates and latencies."""

    def __init__(self, config: Optional[MonitorConfig] = None, ros_config: Optional[ROS2Config] = None):
        self.config = config or get_config().monitor
        self.ros_config = ros_config or get_config().ros2

        # Initialize node
        super().__init__(self.ros_config.node_name)

        # Topic tracker
        self.tracker = TopicTracker(self.config)

        # Latency analyzer
        self.latency_analyzer = LatencyAnalyzer()

        # Subscriptions
        self._subscriptions: Dict[str, Subscription] = {}
        self._callback_group = ReentrantCallbackGroup()

        # QoS profile
        self._qos = self._create_qos()

        # External callbacks
        self._external_callbacks: List[Callable[[str, TopicSample], None]] = []

        # Register default chains
        self._setup_default_chains()

        logger.info(f"ROS Monitor Node initialized: {self.ros_config.node_name}")

    def _create_qos(self) -> QoSProfile:
        """Create QoS profile from config."""
        reliability = ReliabilityPolicy.RELIABLE
        if self.ros_config.qos_reliability == "best_effort":
            reliability = ReliabilityPolicy.BEST_EFFORT

        durability = DurabilityPolicy.VOLATILE
        if self.ros_config.qos_durability == "transient_local":
            durability = DurabilityPolicy.TRANSIENT_LOCAL

        return QoSProfile(
            reliability=reliability,
            durability=durability,
            history=HistoryPolicy.KEEP_LAST,
            depth=self.config.qos_depth,
        )

    def _setup_default_chains(self) -> None:
        """Setup default latency chains for common robotics pipelines."""
        # Perception chain
        self.latency_analyzer.register_chain(
            "perception",
            ["/camera/image_raw", "/camera/detection", "/perception/objects"]
        )

        # Navigation chain
        self.latency_analyzer.register_chain(
            "navigation",
            ["/scan", "/odom", "/amcl_pose", "/plan", "/cmd_vel"]
        )

        # Localization chain
        self.latency_analyzer.register_chain(
            "localization",
            ["/scan", "/odom", "/amcl_pose"]
        )

    def start_monitoring(self) -> None:
        """Start monitoring configured topics."""
        for topic in self.config.topics:
            self.subscribe_topic(topic)

        # Register internal callback
        self.tracker.register_callback(self._on_topic_sample)

    def subscribe_topic(self, topic: str, message_type: Optional[str] = None) -> bool:
        """Subscribe to a topic."""
        if topic in self._subscriptions:
            logger.warning(f"Already subscribed to {topic}")
            return True

        try:
            # Try to get message type
            if message_type is None:
                message_type = self._get_topic_type(topic)

            if message_type is None:
                logger.warning(f"Could not determine message type for {topic}, using generic subscription")
                # Create generic subscription
                msg_class = get_message("std_msgs/msg/Header")  # fallback
            else:
                msg_class = get_message(message_type)

            # Create subscription
            sub = self.create_subscription(
                msg_class,
                topic,
                lambda msg, t=topic, mt=message_type: self._message_callback(t, mt, msg),
                self._qos,
                callback_group=self._callback_group,
            )

            self._subscriptions[topic] = sub
            self.tracker.register_topic(topic, message_type or "unknown")
            logger.info(f"Subscribed to {topic} ({message_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to {topic}: {e}")
            return False

    def _get_topic_type(self, topic: str) -> Optional[str]:
        """Get message type for a topic."""
        try:
            topic_names_and_types = self.get_topic_names_and_types()
            for name, types in topic_names_and_types:
                if name == topic and types:
                    return types[0]
        except Exception:
            pass
        return None

    def _message_callback(self, topic: str, message_type: str, msg) -> None:
        """Handle incoming message."""
        timestamp_ns = now_ns()

        # Extract header timestamp if available
        header_stamp_ns = None
        if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
            stamp = msg.header.stamp
            header_stamp_ns = stamp.sec * 1_000_000_000 + stamp.nanosec

        # Estimate message size
        size_bytes = 0
        try:
            import sys
            size_bytes = sys.getsizeof(msg)
        except Exception:
            pass

        # Process through tracker
        self.tracker.on_message(topic, message_type, timestamp_ns, header_stamp_ns, size_bytes)

        # Process through latency analyzer
        if header_stamp_ns:
            for chain_name, chain_topics in self.latency_analyzer._chains.items():
                if topic in chain_topics:
                    self.latency_analyzer.add_sample(chain_name, topic, timestamp_ns, header_stamp_ns)

    def _on_topic_sample(self, topic: str, sample: TopicSample) -> None:
        """Forward sample to external callbacks."""
        for callback in self._external_callbacks:
            try:
                callback(topic, sample)
            except Exception as e:
                logger.error(f"External callback error: {e}")

    def register_external_callback(self, callback: Callable[[str, TopicSample], None]) -> None:
        """Register external callback for topic samples."""
        self._external_callbacks.append(callback)

    def get_topic_stats(self, topic: str) -> Optional[Dict]:
        """Get statistics for a topic."""
        stats = self.tracker.get_stats(topic)
        return stats.to_dict() if stats else None

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get all topic statistics."""
        return {topic: stats.to_dict() for topic, stats in self.tracker.get_all_stats().items()}

    def get_deadline_status(self) -> Dict[str, Dict]:
        """Get deadline miss status."""
        return self.tracker.get_deadline_status()

    def get_chain_latency(self, chain_name: str) -> Optional[Dict]:
        """Get chain latency analysis."""
        return self.latency_analyzer.get_chain_latency(chain_name)

    def get_subscribed_topics(self) -> List[str]:
        """Get list of subscribed topics."""
        return list(self._subscriptions.keys())

    def shutdown(self) -> None:
        """Clean shutdown."""
        for sub in self._subscriptions.values():
            self.destroy_subscription(sub)
        self._subscriptions.clear()
        logger.info("ROS Monitor Node shutdown")


def create_ros_monitor(config: Optional[MonitorConfig] = None,
                       ros_config: Optional[ROS2Config] = None) -> ROSMonitorNode:
    """Factory function to create ROS monitor node."""
    return ROSMonitorNode(config, ros_config)


def spin_ros_monitor(node: ROSMonitorNode) -> None:
    """Spin the ROS monitor node in a separate thread."""
    def spin_thread():
        rclpy.spin(node)

    thread = threading.Thread(target=spin_thread, daemon=True)
    thread.start()
    return thread