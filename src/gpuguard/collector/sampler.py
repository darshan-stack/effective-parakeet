"""GPU state sampler with ring buffer for historical data."""
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import time

from gpuguard.collector.metrics import GPUState, GPUInfo
from gpuguard.utils.time_utils import now_ns, TimeWindow
from gpuguard.utils.logging import get_logger

logger = get_logger("collector.sampler")


@dataclass
class GPUSamplerStats:
    """Sampler statistics."""
    total_samples: int = 0
    buffer_overflows: int = 0
    last_sample_ns: int = 0


class GPUSampler:
    """Ring buffer sampler for GPU state history."""

    def __init__(self, buffer_size: int = 10000, max_gpus: int = 8):
        self.buffer_size = buffer_size
        self.max_gpus = max_gpus

        # Per-GPU ring buffers
        self._buffers: Dict[int, deque] = {}
        self._lock = threading.RLock()

        # Time windows for quick statistics
        self._time_windows: Dict[int, TimeWindow] = {}

        # GPU info cache
        self._gpu_infos: Dict[int, GPUInfo] = {}

        # Stats
        self._stats = GPUSamplerStats()

        # Callbacks for new samples
        self._callbacks: List[Callable[[int, GPUState], None]] = []

    def set_gpu_info(self, gpu_id: int, info: GPUInfo) -> None:
        """Set static GPU info."""
        with self._lock:
            self._gpu_infos[gpu_id] = info
            if gpu_id not in self._buffers:
                self._buffers[gpu_id] = deque(maxlen=self.buffer_size)
                self._time_windows[gpu_id] = TimeWindow(60.0)  # 60 second window

    def add_sample(self, state: GPUState) -> None:
        """Add a GPU state sample."""
        gpu_id = state.gpu_id

        with self._lock:
            # Ensure buffer exists
            if gpu_id not in self._buffers:
                self._buffers[gpu_id] = deque(maxlen=self.buffer_size)
                self._time_windows[gpu_id] = TimeWindow(60.0)

            # Check for overflow
            if len(self._buffers[gpu_id]) == self.buffer_size:
                self._stats.buffer_overflows += 1

            # Add to buffer
            self._buffers[gpu_id].append(state)

            # Update time window (using memory usage as proxy metric)
            self._time_windows[gpu_id].add(state.timestamp_ns, state.memory_used_pct)

            # Update stats
            self._stats.total_samples += 1
            self._stats.last_sample_ns = state.timestamp_ns

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(gpu_id, state)
                except Exception as e:
                    logger.error(f"Sampler callback error: {e}")

    def register_callback(self, callback: Callable[[int, GPUState], None]) -> None:
        """Register callback for new samples."""
        self._callbacks.append(callback)

    def get_latest(self, gpu_id: int) -> Optional[GPUState]:
        """Get latest sample for GPU."""
        with self._lock:
            buffer = self._buffers.get(gpu_id)
            if buffer:
                return buffer[-1]
        return None

    def get_history(self, gpu_id: int, max_samples: Optional[int] = None) -> List[GPUState]:
        """Get historical samples for GPU."""
        with self._lock:
            buffer = self._buffers.get(gpu_id)
            if not buffer:
                return []
            if max_samples:
                return list(buffer)[-max_samples:]
            return list(buffer)

    def get_time_range(self, gpu_id: int, start_ns: int, end_ns: int) -> List[GPUState]:
        """Get samples within time range."""
        with self._lock:
            buffer = self._buffers.get(gpu_id)
            if not buffer:
                return []
            return [s for s in buffer if start_ns <= s.timestamp_ns <= end_ns]

    def get_window_stats(self, gpu_id: int) -> Dict[str, float]:
        """Get statistics for the current time window."""
        with self._lock:
            window = self._time_windows.get(gpu_id)
            if not window:
                return {}

            return {
                "mean": window.mean() or 0.0,
                "std": window.std() or 0.0,
                "min": min(window.get_values()) if window.get_values() else 0.0,
                "max": max(window.get_values()) if window.get_values() else 0.0,
                "rate_hz": window.rate_hz(),
                "count": len(window.get_values()),
                "p50": window.percentile(50) or 0.0,
                "p90": window.percentile(90) or 0.0,
                "p95": window.percentile(95) or 0.0,
                "p99": window.percentile(99) or 0.0,
            }

    def get_gpu_info(self, gpu_id: int) -> Optional[GPUInfo]:
        """Get GPU info."""
        return self._gpu_infos.get(gpu_id)

    def get_all_gpu_ids(self) -> List[int]:
        """Get all GPU IDs with data."""
        with self._lock:
            return list(self._buffers.keys())

    def get_stats(self) -> GPUSamplerStats:
        """Get sampler statistics."""
        return self._stats

    def clear(self, gpu_id: Optional[int] = None) -> None:
        """Clear buffers."""
        with self._lock:
            if gpu_id is not None:
                if gpu_id in self._buffers:
                    self._buffers[gpu_id].clear()
                    self._time_windows[gpu_id].clear()
            else:
                for buf in self._buffers.values():
                    buf.clear()
                for tw in self._time_windows.values():
                    tw.clear()

    def export_dataframe(self, gpu_id: int):
        """Export GPU history as pandas DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            logger.warning("pandas not available for DataFrame export")
            return None

        with self._lock:
            buffer = self._buffers.get(gpu_id)
            if not buffer:
                return None

            data = [s.to_dict() for s in buffer]
            return pd.DataFrame(data)


class MetricAggregator:
    """Aggregate metrics across time windows."""

    def __init__(self, window_s: float = 10.0):
        self.window_s = window_s
        self.window_ns = int(window_s * 1_000_000_000)
        self._samples: Dict[int, List[GPUState]] = {}
        self._lock = threading.RLock()

    def add(self, state: GPUState) -> None:
        """Add sample to aggregator."""
        gpu_id = state.gpu_id
        with self._lock:
            if gpu_id not in self._samples:
                self._samples[gpu_id] = []
            self._samples[gpu_id].append(state)
            self._prune(gpu_id, state.timestamp_ns)

    def _prune(self, gpu_id: int, current_ns: int) -> None:
        """Remove old samples."""
        cutoff = current_ns - self.window_ns
        samples = self._samples.get(gpu_id, [])
        self._samples[gpu_id] = [s for s in samples if s.timestamp_ns >= cutoff]

    def get_aggregated(self, gpu_id: int) -> Dict[str, float]:
        """Get aggregated metrics for window."""
        with self._lock:
            samples = self._samples.get(gpu_id, [])
            if not samples:
                return {}

            # Compute aggregations
            n = len(samples)
            return {
                "count": n,
                "memory_used_pct_avg": sum(s.memory_used_pct for s in samples) / n,
                "memory_used_pct_max": max(s.memory_used_pct for s in samples),
                "utilization_gpu_avg": sum(s.utilization_gpu for s in samples) / n,
                "utilization_gpu_max": max(s.utilization_gpu for s in samples),
                "temperature_gpu_avg": sum(s.temperature_gpu for s in samples) / n,
                "temperature_gpu_max": max(s.temperature_gpu for s in samples),
                "power_draw_avg": sum(s.power_draw for s in samples) / n,
                "power_draw_max": max(s.power_draw for s in samples),
                "clock_graphics_avg": sum(s.clock_graphics for s in samples) / n,
                "clock_graphics_min": min(s.clock_graphics for s in samples),
                "fan_speed_avg": sum(s.fan_speed for s in samples) / n,
                "ecc_errors_total": sum(s.ecc_errors_volatile for s in samples),
            }

    def clear(self) -> None:
        """Clear all samples."""
        with self._lock:
            self._samples.clear()