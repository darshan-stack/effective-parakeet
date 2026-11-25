"""Time synchronization utilities for GPUGuard."""
import time
from dataclasses import dataclass
from typing import Optional
import threading


@dataclass
class TimeSync:
    """Time synchronization state between clocks."""
    offset_ns: int = 0
    drift_ppm: float = 0.0
    last_sync_time: float = 0.0
    samples: int = 0

    def apply(self, timestamp_ns: int) -> int:
        """Apply synchronization offset to a timestamp."""
        return timestamp_ns + self.offset_ns

    def reverse(self, timestamp_ns: int) -> int:
        """Reverse synchronization offset from a timestamp."""
        return timestamp_ns - self.offset_ns


class ClockSync:
    """Synchronize multiple clock sources using NTP-style algorithm."""

    def __init__(self, max_samples: int = 100):
        self.max_samples = max_samples
        self.offsets: list[int] = []
        self.delays: list[int] = []
        self.lock = threading.Lock()
        self.sync = TimeSync()

    def add_sample(self, local_send_ns: int, remote_recv_ns: int,
                   remote_send_ns: int, local_recv_ns: int) -> None:
        """Add a synchronization sample (NTP-style 4-timestamp)."""
        # Calculate offset and delay
        offset = ((remote_recv_ns - local_send_ns) + (remote_send_ns - local_recv_ns)) // 2
        delay = (local_recv_ns - local_send_ns) - (remote_send_ns - remote_recv_ns)

        with self.lock:
            self.offsets.append(offset)
            self.delays.append(delay)

            if len(self.offsets) > self.max_samples:
                self.offsets.pop(0)
                self.delays.pop(0)

            self._recompute()

    def _recompute(self) -> None:
        """Recompute synchronization state from samples."""
        if not self.offsets:
            return

        # Use median offset for robustness
        sorted_offsets = sorted(self.offsets)
        n = len(sorted_offsets)
        if n % 2 == 0:
            median_offset = (sorted_offsets[n//2 - 1] + sorted_offsets[n//2]) // 2
        else:
            median_offset = sorted_offsets[n//2]

        # Estimate drift from offset changes over time
        if len(self.offsets) > 10:
            recent = sorted_offsets[-10:]
            older = sorted_offsets[:10]
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            time_span = len(self.offsets)  # Approximate sample count as time
            if time_span > 0:
                drift_per_sample = (recent_avg - older_avg) / time_span
                # Convert to ppm (assuming ~10Hz sampling)
                self.sync.drift_ppm = drift_per_sample * 1e6 / 1e8  # Rough conversion

        self.sync.offset_ns = median_offset
        self.sync.samples = len(self.offsets)

    def get_sync(self) -> TimeSync:
        """Get current synchronization state."""
        with self.lock:
            return TimeSync(
                offset_ns=self.sync.offset_ns,
                drift_ppm=self.sync.drift_ppm,
                last_sync_time=self.sync.last_sync_time,
                samples=self.sync.samples,
            )


# High-resolution time functions
def now_ns() -> int:
    """Get current time in nanoseconds (monotonic)."""
    return time.time_ns()


def now_s() -> float:
    """Get current time in seconds (monotonic)."""
    return time.monotonic()


def ns_to_s(ns: int) -> float:
    """Convert nanoseconds to seconds."""
    return ns / 1_000_000_000.0


def s_to_ns(s: float) -> int:
    """Convert seconds to nanoseconds."""
    return int(s * 1_000_000_000)


class RateLimiter:
    """Rate limiter for consistent sampling."""

    def __init__(self, hz: float):
        self.interval = 1.0 / hz
        self.next_time = time.monotonic()

    def sleep(self) -> None:
        """Sleep to maintain rate."""
        now = time.monotonic()
        if now < self.next_time:
            time.sleep(self.next_time - now)
        self.next_time = max(self.next_time + self.interval, now + self.interval)

    def reset(self) -> None:
        """Reset the rate limiter."""
        self.next_time = time.monotonic()


class TimeWindow:
    """Sliding time window for data aggregation."""

    def __init__(self, window_s: float):
        self.window_s = window_s
        self.window_ns = int(window_s * 1_000_000_000)
        self.data: list[tuple[int, float]] = []  # (timestamp_ns, value)

    def add(self, timestamp_ns: int, value: float) -> None:
        """Add a data point."""
        self.data.append((timestamp_ns, value))
        self._prune(timestamp_ns)

    def _prune(self, current_ns: int) -> None:
        """Remove data outside the window."""
        cutoff = current_ns - self.window_ns
        self.data = [(t, v) for t, v in self.data if t >= cutoff]

    def get_values(self) -> list[float]:
        """Get all values in window."""
        return [v for _, v in self.data]

    def get_timestamps(self) -> list[int]:
        """Get all timestamps in window."""
        return [t for t, _ in self.data]

    def mean(self) -> Optional[float]:
        """Calculate mean of values in window."""
        values = self.get_values()
        return sum(values) / len(values) if values else None

    def std(self) -> Optional[float]:
        """Calculate standard deviation of values in window."""
        values = self.get_values()
        if len(values) < 2:
            return None
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return variance ** 0.5

    def percentile(self, p: float) -> Optional[float]:
        """Calculate percentile of values in window."""
        values = sorted(self.get_values())
        if not values:
            return None
        idx = int(len(values) * p / 100)
        idx = min(idx, len(values) - 1)
        return values[idx]

    def rate_hz(self) -> float:
        """Calculate approximate rate in Hz."""
        if len(self.data) < 2:
            return 0.0
        time_span = (self.data[-1][0] - self.data[0][0]) / 1_000_000_000.0
        if time_span <= 0:
            return 0.0
        return (len(self.data) - 1) / time_span

    def clear(self) -> None:
        """Clear all data."""
        self.data.clear()