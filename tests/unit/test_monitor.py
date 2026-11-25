"""Unit tests for ROS 2 monitor."""
import pytest
import time
from unittest.mock import Mock, patch

from gpuguard.monitor.topic_tracker import TopicTracker, TopicStats, LatencyAnalyzer
from gpuguard.utils.config import MonitorConfig
from gpuguard.utils.time_utils import now_ns, TimeWindow


class TestTopicTracker:
    """Test topic tracker."""

    @pytest.fixture
    def config(self):
        return MonitorConfig(
            topics=["/test_topic"],
            deadline_ms=33,
            window_size=100,
            hz_window_s=5.0,
        )

    @pytest.fixture
    def tracker(self, config):
        return TopicTracker(config)

    def test_register_topic(self, tracker):
        tracker.register_topic("/new_topic", "std_msgs/String", deadline_ms=50)
        assert "/new_topic" in tracker.get_tracked_topics()

    def test_on_message(self, tracker):
        ts = now_ns()
        tracker.on_message("/test_topic", "std_msgs/String", ts, ts - 5_000_000, 1024)

        stats = tracker.get_stats("/test_topic")
        assert stats is not None
        assert stats.sample_count == 1
        assert stats.message_type == "std_msgs/String"
        assert stats.avg_latency_ns == 5_000_000

    def test_rate_calculation(self, tracker):
        base = now_ns()
        for i in range(10):
            tracker.on_message("/test_topic", "std_msgs/String", base + i * 100_000_000)

        stats = tracker.get_stats("/test_topic")
        assert stats.sample_count == 10
        # 10 messages over 1 second = 10 Hz (approximately)
        assert 9.0 < stats.current_hz < 11.0

    def test_deadline_detection(self, tracker):
        base = now_ns()
        # Send messages with 100ms gap (deadline is 33ms)
        tracker.on_message("/test_topic", "std_msgs/String", base)
        tracker.on_message("/test_topic", "std_msgs/String", base + 100_000_000)

        stats = tracker.get_stats("/test_topic")
        assert stats.deadline_misses == 1
        assert stats.consecutive_misses == 1

        # Next message on time
        tracker.on_message("/test_topic", "std_msgs/String", base + 133_000_000)
        stats = tracker.get_stats("/test_topic")
        assert stats.consecutive_misses == 0

    def test_latency_percentiles(self, tracker):
        base = now_ns()
        latencies = [1, 2, 3, 4, 5, 10, 20, 50, 100, 200]  # ms
        for lat in latencies:
            tracker.on_message("/test_topic", "std_msgs/String", base, base - lat * 1_000_000)

        stats = tracker.get_stats("/test_topic")
        assert stats.p50_latency_ms == pytest.approx(5, rel=0.2)
        assert stats.p90_latency_ms == pytest.approx(100, rel=0.2)
        assert stats.p99_latency_ms == pytest.approx(200, rel=0.2)

    def test_deadline_status(self, tracker):
        base = now_ns()
        tracker.on_message("/test_topic", "std_msgs/String", base)
        tracker.on_message("/test_topic", "std_msgs/String", base + 100_000_000)

        status = tracker.get_deadline_status()
        assert "/test_topic" in status
        assert status["/test_topic"]["misses"] == 1
        assert status["/test_topic"]["consecutive_misses"] == 1

    def test_clear(self, tracker):
        base = now_ns()
        tracker.on_message("/test_topic", "std_msgs/String", base)
        tracker.clear("/test_topic")

        stats = tracker.get_stats("/test_topic")
        assert stats.sample_count == 0


class TestTimeWindow:
    """Test time window utility."""

    def test_basic_stats(self):
        tw = TimeWindow(10.0)
        base = now_ns()

        for i in range(100):
            tw.add(base + i * 100_000_000, float(i))

        assert tw.mean() == 49.5
        assert tw.std() == pytest.approx(28.86, rel=0.1)
        assert tw.percentile(50) == 49.5
        assert tw.percentile(90) == 89
        assert tw.rate_hz() == pytest.approx(10.0, rel=0.1)

    def test_window_pruning(self):
        tw = TimeWindow(1.0)  # 1 second window
        base = now_ns()

        tw.add(base, 1.0)
        tw.add(base + 500_000_000, 2.0)  # 0.5s later
        tw.add(base + 1_500_000_000, 3.0)  # 1.5s later - first should be pruned

        assert len(tw.get_values()) == 2
        assert 1.0 not in tw.get_values()


class TestLatencyAnalyzer:
    """Test latency chain analyzer."""

    def test_chain_registration(self):
        analyzer = LatencyAnalyzer()
        analyzer.register_chain("test_chain", ["/a", "/b", "/c"])
        assert "test_chain" in analyzer._chains

    def test_chain_latency(self):
        analyzer = LatencyAnalyzer()
        analyzer.register_chain("perception", ["/camera/image", "/detections"])

        base = now_ns()
        analyzer.add_sample("perception", "/camera/image", base, base - 10_000_000)
        analyzer.add_sample("perception", "/detections", base + 20_000_000, base + 10_000_000)

        result = analyzer.get_chain_latency("perception")
        assert result is not None
        assert "/camera/image" in result["topics"]
        assert "/detections" in result["topics"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])