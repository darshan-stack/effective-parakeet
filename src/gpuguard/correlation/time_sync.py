"""Time synchronization for correlating GPU and ROS 2 data streams."""
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from gpuguard.utils.time_utils import now_ns, TimeSync, ClockSync
from gpuguard.utils.logging import get_logger

logger = get_logger("correlation.time_sync")


@dataclass
class SyncSample:
    """A pair of synchronized timestamps with values."""
    gpu_timestamp_ns: int
    ros_timestamp_ns: int
    gpu_metric: str
    ros_topic: str
    gpu_value: float = 0.0
    ros_value: float = 0.0
    confidence: float = 1.0


class TimeSynchronizer:
    """Synchronize GPU and ROS 2 timestamp streams."""

    def __init__(self, tolerance_ms: int = 5, max_samples: int = 1000):
        self.tolerance_ns = tolerance_ms * 1_000_000
        self.max_samples = max_samples

        # Clock sync using NTP-style algorithm
        self.clock_sync = ClockSync(max_samples=max_samples)

        # Stream buffers
        self._gpu_buffer: Dict[str, List[Tuple[int, float]]] = {}  # metric -> [(timestamp, value)]
        self._ros_buffer: Dict[str, List[Tuple[int, float]]] = {}  # topic -> [(timestamp, value)]

        # Synchronized pairs
        self._sync_pairs: List[SyncSample] = []

        # Lock
        self._lock = threading.RLock()

        # Callbacks
        self._callbacks: List[callable] = []

    def add_gpu_sample(self, metric: str, timestamp_ns: int, value: float) -> None:
        """Add GPU metric sample."""
        with self._lock:
            if metric not in self._gpu_buffer:
                self._gpu_buffer[metric] = []
            self._gpu_buffer[metric].append((timestamp_ns, value))

            # Trim buffer
            if len(self._gpu_buffer[metric]) > self.max_samples:
                self._gpu_buffer[metric] = self._gpu_buffer[metric][-self.max_samples:]

            # Try to match with ROS samples
            self._try_match(metric, timestamp_ns, value, is_gpu=True)

    def add_ros_sample(self, topic: str, timestamp_ns: int, value: float) -> None:
        """Add ROS topic sample."""
        with self._lock:
            if topic not in self._ros_buffer:
                self._ros_buffer[topic] = []
            self._ros_buffer[topic].append((timestamp_ns, value))

            # Trim buffer
            if len(self._ros_buffer[topic]) > self.max_samples:
                self._ros_buffer[topic] = self._ros_buffer[topic][-self.max_samples:]

            # Try to match with GPU samples
            self._try_match(topic, timestamp_ns, value, is_gpu=False)

    def _try_match(self, key: str, timestamp_ns: int, value: float, is_gpu: bool) -> None:
        """Try to find matching sample from the other stream."""
        if is_gpu:
            gpu_metric = key
            gpu_time = timestamp_ns
            gpu_value = value

            # Find closest ROS sample for each topic
            for topic, ros_samples in self._ros_buffer.items():
                if not ros_samples:
                    continue

                # Binary search for closest timestamp
                ros_times = [s[0] for s in ros_samples]
                idx = np.searchsorted(ros_times, gpu_time)

                best_match = None
                best_diff = self.tolerance_ns + 1

                # Check idx and idx-1
                for check_idx in [idx, idx - 1]:
                    if 0 <= check_idx < len(ros_samples):
                        ros_time, ros_value = ros_samples[check_idx]
                        diff = abs(gpu_time - ros_time)
                        if diff < best_diff:
                            best_diff = diff
                            best_match = (ros_time, ros_value)

                if best_match and best_diff <= self.tolerance_ns:
                    ros_time, ros_value = best_match
                    confidence = 1.0 - (best_diff / self.tolerance_ns)

                    pair = SyncSample(
                        gpu_timestamp_ns=gpu_time,
                        ros_timestamp_ns=ros_time,
                        gpu_metric=gpu_metric,
                        ros_topic=topic,
                        gpu_value=gpu_value,
                        ros_value=ros_value,
                        confidence=confidence,
                    )
                    self._sync_pairs.append(pair)
                    self._notify_callbacks(pair)

        else:
            ros_topic = key
            ros_time = timestamp_ns
            ros_value = value

            # Find closest GPU sample for each metric
            for metric, gpu_samples in self._gpu_buffer.items():
                if not gpu_samples:
                    continue

                gpu_times = [s[0] for s in gpu_samples]
                idx = np.searchsorted(gpu_times, ros_time)

                best_match = None
                best_diff = self.tolerance_ns + 1

                for check_idx in [idx, idx - 1]:
                    if 0 <= check_idx < len(gpu_samples):
                        gpu_time, gpu_value = gpu_samples[check_idx]
                        diff = abs(gpu_time - ros_time)
                        if diff < best_diff:
                            best_diff = diff
                            best_match = (gpu_time, gpu_value)

                if best_match and best_diff <= self.tolerance_ns:
                    gpu_time, gpu_value = best_match
                    confidence = 1.0 - (best_diff / self.tolerance_ns)

                    pair = SyncSample(
                        gpu_timestamp_ns=gpu_time,
                        ros_timestamp_ns=ros_time,
                        gpu_metric=metric,
                        ros_topic=ros_topic,
                        gpu_value=gpu_value,
                        ros_value=ros_value,
                        confidence=confidence,
                    )
                    self._sync_pairs.append(pair)
                    self._notify_callbacks(pair)

        # Trim sync pairs
        if len(self._sync_pairs) > self.max_samples:
            self._sync_pairs = self._sync_pairs[-self.max_samples:]

    def register_callback(self, callback: callable) -> None:
        """Register callback for synchronized pairs."""
        self._callbacks.append(callback)

    def _notify_callbacks(self, pair: SyncSample) -> None:
        """Notify all callbacks."""
        for callback in self._callbacks:
            try:
                callback(pair)
            except Exception as e:
                logger.error(f"Time sync callback error: {e}")

    def get_sync_pairs(self, gpu_metric: Optional[str] = None,
                       ros_topic: Optional[str] = None,
                       max_age_ns: Optional[int] = None) -> List[SyncSample]:
        """Get synchronized pairs with optional filtering."""
        with self._lock:
            pairs = self._sync_pairs

            if gpu_metric:
                pairs = [p for p in pairs if p.gpu_metric == gpu_metric]
            if ros_topic:
                pairs = [p for p in pairs if p.ros_topic == ros_topic]
            if max_age_ns:
                now = now_ns()
                pairs = [p for p in pairs if now - p.gpu_timestamp_ns <= max_age_ns]

            return pairs

    def get_time_sync(self) -> TimeSync:
        """Get current time synchronization state."""
        return self.clock_sync.get_sync()

    def add_manual_sync(self, gpu_timestamp_ns: int, ros_timestamp_ns: int) -> None:
        """Manually add a synchronization point (e.g., from shared hardware trigger)."""
        # Add as a clock sync sample (4-timestamp NTP style approximation)
        # We use the same timestamp for send/recv as approximation
        self.clock_sync.add_sample(
            local_send_ns=gpu_timestamp_ns,
            remote_recv_ns=ros_timestamp_ns,
            remote_send_ns=ros_timestamp_ns,
            local_recv_ns=gpu_timestamp_ns,
        )

    def clear(self) -> None:
        """Clear all buffers."""
        with self._lock:
            self._gpu_buffer.clear()
            self._ros_buffer.clear()
            self._sync_pairs.clear()


class StreamAligner:
    """Align multiple data streams to a common time base."""

    def __init__(self, reference_stream: str = "gpu", tolerance_ms: int = 5):
        self.reference_stream = reference_stream
        self.tolerance_ns = tolerance_ms * 1_000_000
        self._streams: Dict[str, List[Tuple[int, Any]]] = {}
        self._lock = threading.RLock()

    def add_sample(self, stream: str, timestamp_ns: int, data: Any) -> None:
        """Add sample to a stream."""
        with self._lock:
            if stream not in self._streams:
                self._streams[stream] = []
            self._streams[stream].append((timestamp_ns, data))

    def get_aligned(self, target_time_ns: int, max_streams: Optional[int] = None) -> Dict[str, Any]:
        """Get samples from all streams aligned to target time."""
        with self._lock:
            result = {}

            for stream, samples in self._streams.items():
                if not samples:
                    continue

                times = [s[0] for s in samples]
                idx = np.searchsorted(times, target_time_ns)

                best_idx = None
                best_diff = self.tolerance_ns + 1

                for check_idx in [idx, idx - 1]:
                    if 0 <= check_idx < len(samples):
                        diff = abs(samples[check_idx][0] - target_time_ns)
                        if diff < best_diff:
                            best_diff = diff
                            best_idx = check_idx

                if best_idx is not None:
                    result[stream] = {
                        "timestamp_ns": samples[best_idx][0],
                        "data": samples[best_idx][1],
                        "offset_ns": samples[best_idx][0] - target_time_ns,
                    }

            return result

    def get_latest_aligned(self) -> Dict[str, Any]:
        """Get latest samples from all streams aligned to the reference stream's latest time."""
        with self._lock:
            if self.reference_stream not in self._streams:
                return {}

            ref_samples = self._streams[self.reference_stream]
            if not ref_samples:
                return {}

            latest_ref_time = ref_samples[-1][0]
            return self.get_aligned(latest_ref_time)