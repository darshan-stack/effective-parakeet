"""ROS 2 topic tracking and latency analysis."""
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from collections import deque
import uuid

from gpuguard.utils.time_utils import now_ns, TimeWindow
from gpuguard.utils.logging import get_logger
from gpuguard.utils.config import get_config, MonitorConfig

logger = get_logger("monitor.topic_tracker")


@dataclass
class TopicSample:
    """Single topic message sample."""
    timestamp_ns: int
    topic: str
    message_type: str
    size_bytes: int
    latency_ns: Optional[int] = None  # End-to-end latency if available
    header_stamp_ns: Optional[int] = None  # ROS header timestamp


@dataclass
class TopicStats:
    """Statistics for a topic."""
    topic: str
    message_type: str
    sample_count: int = 0
    first_timestamp_ns: int = 0
    last_timestamp_ns: int = 0

    # Rate
    current_hz: float = 0.0
    avg_hz: float = 0.0
    min_hz: float = float('inf')
    max_hz: float = 0.0

    # Latency (ns)
    avg_latency_ns: float = 0.0
    min_latency_ns: int = 0
    max_latency_ns: int = 0
    p50_latency_ns: float = 0.0
    p90_latency_ns: float = 0.0
    p95_latency_ns: float = 0.0
    p99_latency_ns: float = 0.0

    # Deadline tracking
    deadline_ms: float = 50.0
    deadline_misses: int = 0
    consecutive_misses: int = 0
    last_deadline_check_ns: int = 0

    # Message size
    avg_size_bytes: float = 0.0
    max_size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "message_type": self.message_type,
            "sample_count": self.sample_count,
            "current_hz": self.current_hz,
            "avg_hz": self.avg_hz,
            "min_hz": self.min_hz if self.min_hz != float('inf') else 0.0,
            "max_hz": self.max_hz,
            "avg_latency_ms": self.avg_latency_ns / 1_000_000.0,
            "min_latency_ms": self.min_latency_ns / 1_000_000.0,
            "max_latency_ms": self.max_latency_ns / 1_000_000.0,
            "p50_latency_ms": self.p50_latency_ns / 1_000_000.0,
            "p90_latency_ms": self.p90_latency_ns / 1_000_000.0,
            "p95_latency_ms": self.p95_latency_ns / 1_000_000.0,
            "p99_latency_ms": self.p99_latency_ns / 1_000_000.0,
            "deadline_ms": self.deadline_ms,
            "deadline_misses": self.deadline_misses,
            "consecutive_misses": self.consecutive_misses,
            "avg_size_bytes": self.avg_size_bytes,
            "max_size_bytes": self.max_size_bytes,
        }


class TopicTracker:
    """Tracks ROS 2 topic statistics and deadlines."""

    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or get_config().monitor
        self._lock = threading.RLock()

        # Topic configurations
        self._tracked_topics: Dict[str, Dict] = {}
        for topic in self.config.topics:
            self._tracked_topics[topic] = {
                "deadline_ms": self.config.deadline_ms,
                "message_type": "unknown",
            }

        # Statistics
        self._stats: Dict[str, TopicStats] = {}

        # Time windows for rate calculation
        self._windows: Dict[str, TimeWindow] = {}

        # Latency windows
        self._latency_windows: Dict[str, TimeWindow] = {}

        # Message buffers for deadline detection
        self._last_msg_time: Dict[str, int] = {}

        # Callbacks
        self._callbacks: List[Callable[[str, TopicSample], None]] = []

    def register_topic(self, topic: str, message_type: str, deadline_ms: Optional[float] = None) -> None:
        """Register a topic for tracking."""
        with self._lock:
            self._tracked_topics[topic] = {
                "deadline_ms": deadline_ms or self.config.deadline_ms,
                "message_type": message_type,
            }
            if topic not in self._stats:
                self._stats[topic] = TopicStats(
                    topic=topic,
                    message_type=message_type,
                    deadline_ms=deadline_ms or self.config.deadline_ms,
                )
            if topic not in self._windows:
                self._windows[topic] = TimeWindow(self.config.hz_window_s)
            if topic not in self._latency_windows:
                self._latency_windows[topic] = TimeWindow(self.config.hz_window_s)

    def on_message(self, topic: str, message_type: str, timestamp_ns: Optional[int] = None,
                   header_stamp_ns: Optional[int] = None, size_bytes: int = 0) -> None:
        """Process a new message."""
        if timestamp_ns is None:
            timestamp_ns = now_ns()

        with self._lock:
            # Register if new
            if topic not in self._tracked_topics:
                self.register_topic(topic, message_type)

            # Get or create stats
            if topic not in self._stats:
                self._stats[topic] = TopicStats(
                    topic=topic,
                    message_type=message_type,
                    deadline_ms=self._tracked_topics[topic]["deadline_ms"],
                )

            stats = self._stats[topic]
            stats.message_type = message_type

            # Update rate window
            if topic not in self._windows:
                self._windows[topic] = TimeWindow(self.config.hz_window_s)
            self._windows[topic].add(timestamp_ns, 1.0)

            # Update latency if header stamp available
            latency_ns = None
            if header_stamp_ns is not None:
                latency_ns = timestamp_ns - header_stamp_ns
                if latency_ns >= 0:
                    if topic not in self._latency_windows:
                        self._latency_windows[topic] = TimeWindow(self.config.hz_window_s)
                    self._latency_windows[topic].add(timestamp_ns, latency_ns)

            # Deadline checking
            deadline_ns = int(self._tracked_topics[topic]["deadline_ms"] * 1_000_000)
            last_time = self._last_msg_time.get(topic, 0)

            if last_time > 0:
                interval_ns = timestamp_ns - last_time
                if interval_ns > deadline_ns * 2:  # Missed deadline
                    stats.deadline_misses += 1
                    stats.consecutive_misses += 1
                else:
                    stats.consecutive_misses = 0

            self._last_msg_time[topic] = timestamp_ns

            # Update stats
            if stats.sample_count == 0:
                stats.first_timestamp_ns = timestamp_ns
            stats.last_timestamp_ns = timestamp_ns
            stats.sample_count += 1

            # Recalculate rate
            window = self._windows[topic]
            stats.current_hz = window.rate_hz()
            stats.avg_hz = stats.current_hz
            stats.min_hz = min(stats.min_hz, stats.current_hz) if stats.min_hz != float('inf') else stats.current_hz
            stats.max_hz = max(stats.max_hz, stats.current_hz)

            # Recalculate latency percentiles
            if topic in self._latency_windows:
                lat_window = self._latency_windows[topic]
                latencies = sorted(lat_window.get_values())
                if latencies:
                    stats.avg_latency_ns = sum(latencies) / len(latencies)
                    stats.min_latency_ns = latencies[0]
                    stats.max_latency_ns = latencies[-1]
                    stats.p50_latency_ns = latencies[len(latencies) // 2]
                    stats.p90_latency_ns = latencies[int(len(latencies) * 0.9)]
                    stats.p95_latency_ns = latencies[int(len(latencies) * 0.95)]
                    stats.p99_latency_ns = latencies[int(len(latencies) * 0.99)]

            # Update size stats
            if size_bytes > 0:
                total_size = stats.avg_size_bytes * (stats.sample_count - 1) + size_bytes
                stats.avg_size_bytes = total_size / stats.sample_count
                stats.max_size_bytes = max(stats.max_size_bytes, size_bytes)

            # Create sample for callbacks
            sample = TopicSample(
                timestamp_ns=timestamp_ns,
                topic=topic,
                message_type=message_type,
                size_bytes=size_bytes,
                latency_ns=latency_ns,
                header_stamp_ns=header_stamp_ns,
            )

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(topic, sample)
                except Exception as e:
                    logger.error(f"Topic tracker callback error: {e}")

    def register_callback(self, callback: Callable[[str, TopicSample], None]) -> None:
        """Register callback for new messages."""
        self._callbacks.append(callback)

    def get_stats(self, topic: str) -> Optional[TopicStats]:
        """Get statistics for a topic."""
        with self._lock:
            return self._stats.get(topic)

    def get_all_stats(self) -> Dict[str, TopicStats]:
        """Get all topic statistics."""
        with self._lock:
            return dict(self._stats)

    def get_deadline_status(self) -> Dict[str, Dict]:
        """Get deadline miss status for all topics."""
        with self._lock:
            return {
                topic: {
                    "misses": stats.deadline_misses,
                    "consecutive_misses": stats.consecutive_misses,
                    "deadline_ms": stats.deadline_ms,
                    "current_hz": stats.current_hz,
                    "expected_hz": 1000.0 / stats.deadline_ms if stats.deadline_ms > 0 else 0,
                }
                for topic, stats in self._stats.items()
            }

    def get_tracked_topics(self) -> List[str]:
        """Get list of tracked topics."""
        return list(self._tracked_topics.keys())

    def clear(self, topic: Optional[str] = None) -> None:
        """Clear tracking data."""
        with self._lock:
            if topic:
                if topic in self._stats:
                    self._stats[topic] = TopicStats(
                        topic=topic,
                        message_type=self._tracked_topics.get(topic, {}).get("message_type", "unknown"),
                        deadline_ms=self._tracked_topics.get(topic, {}).get("deadline_ms", self.config.deadline_ms),
                    )
                if topic in self._windows:
                    self._windows[topic].clear()
                if topic in self._latency_windows:
                    self._latency_windows[topic].clear()
                self._last_msg_time.pop(topic, None)
            else:
                self._stats.clear()
                self._windows.clear()
                self._latency_windows.clear()
                self._last_msg_time.clear()


class LatencyAnalyzer:
    """Analyze end-to-end latency chains."""

    def __init__(self):
        self._chains: Dict[str, List[str]] = {}  # chain_name -> [topics]
        self._chain_samples: Dict[str, List[Dict]] = {}
        self._lock = threading.RLock()

    def register_chain(self, chain_name: str, topics: List[str]) -> None:
        """Register a latency chain (e.g., sensor -> perception -> planning -> control)."""
        with self._lock:
            self._chains[chain_name] = topics
            self._chain_samples[chain_name] = []

    def add_sample(self, chain_name: str, topic: str, timestamp_ns: int, header_stamp_ns: int) -> None:
        """Add a sample to a chain."""
        with self._lock:
            if chain_name not in self._chain_samples:
                return

            sample = {
                "topic": topic,
                "timestamp_ns": timestamp_ns,
                "header_stamp_ns": header_stamp_ns,
                "latency_ns": timestamp_ns - header_stamp_ns,
            }
            self._chain_samples[chain_name].append(sample)

            # Keep only recent samples (last 1000)
            if len(self._chain_samples[chain_name]) > 1000:
                self._chain_samples[chain_name] = self._chain_samples[chain_name][-1000:]

    def get_chain_latency(self, chain_name: str) -> Optional[Dict]:
        """Get end-to-end latency for a chain."""
        with self._lock:
            samples = self._chain_samples.get(chain_name, [])
            if not samples:
                return None

            # Group by timestamp proximity (assume same message flows through chain)
            # This is a simplified approach - real implementation would use message IDs
            topics = self._chains.get(chain_name, [])
            if not topics:
                return None

            # Calculate per-topic latencies
            topic_latencies = {}
            for topic in topics:
                topic_samples = [s for s in samples if s["topic"] == topic]
                if topic_samples:
                    latencies = [s["latency_ns"] for s in topic_samples]
                    topic_latencies[topic] = {
                        "avg_ms": sum(latencies) / len(latencies) / 1_000_000,
                        "max_ms": max(latencies) / 1_000_000,
                        "min_ms": min(latencies) / 1_000_000,
                        "count": len(latencies),
                    }

            return {
                "chain": chain_name,
                "topics": topic_latencies,
                "total_samples": len(samples),
            }

    def clear_chain(self, chain_name: str) -> None:
        """Clear chain samples."""
        with self._lock:
            if chain_name in self._chain_samples:
                self._chain_samples[chain_name].clear()