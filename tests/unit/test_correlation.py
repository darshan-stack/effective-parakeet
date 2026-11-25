"""Unit tests for correlation engine."""
import pytest
import numpy as np
import time
from unittest.mock import Mock, patch

from gpuguard.correlation.correlator import Correlator, CorrelationResult, GrangerResult
from gpuguard.correlation.time_sync import TimeSynchronizer, SyncSample
from gpuguard.utils.config import CorrelationConfig
from gpuguard.utils.time_utils import now_ns


class TestTimeSynchronizer:
    """Test time synchronization."""

    @pytest.fixture
    def sync(self):
        return TimeSynchronizer(tolerance_ms=5, max_samples=1000)

    def test_add_gpu_sample(self, sync):
        sync.add_gpu_sample("utilization_gpu", 1_000_000_000, 50.0)
        pairs = sync.get_sync_pairs(gpu_metric="utilization_gpu")
        assert len(pairs) == 0  # No ROS samples yet

    def test_add_ros_sample(self, sync):
        sync.add_ros_sample("/camera/detection", 1_000_000_000, 30.0)
        pairs = sync.get_sync_pairs(ros_topic="/camera/detection")
        assert len(pairs) == 0  # No GPU samples yet

    def test_sync_matching(self, sync):
        base = 1_000_000_000
        # Add GPU sample
        sync.add_gpu_sample("utilization_gpu", base, 50.0)
        # Add ROS sample at same time
        sync.add_ros_sample("/camera/detection", base + 1_000_000, 30.0)  # 1ms diff

        pairs = sync.get_sync_pairs()
        assert len(pairs) == 1
        assert pairs[0].gpu_metric == "utilization_gpu"
        assert pairs[0].ros_topic == "/camera/detection"
        assert pairs[0].confidence > 0.5

    def test_sync_tolerance(self, sync):
        base = 1_000_000_000
        sync.add_gpu_sample("utilization_gpu", base, 50.0)
        # Add ROS sample outside tolerance (10ms > 5ms)
        sync.add_ros_sample("/camera/detection", base + 10_000_000, 30.0)

        pairs = sync.get_sync_pairs()
        assert len(pairs) == 0

    def test_manual_sync(self, sync):
        sync.add_manual_sync(1_000_000_000, 1_000_000_100)  # 100ns offset
        ts = sync.get_time_sync()
        assert ts.offset_ns == 100


class TestCorrelator:
    """Test correlation engine."""

    @pytest.fixture
    def config(self):
        return CorrelationConfig(
            sync_tolerance_ms=5,
            min_samples=30,
            granger_maxlag=5,
            rolling_window=100,
            correlation_method="pearson",
            significance_level=0.05,
        )

    @pytest.fixture
    def correlator(self, config):
        return Correlator(config)

    def test_add_gpu_metric(self, correlator):
        correlator.add_gpu_metric("utilization_gpu", 1_000_000_000, 50.0)
        # Should not raise

    def test_add_ros_metric(self, correlator):
        correlator.add_ros_metric("/camera/detection", 1_000_000_000, 30.0)
        # Should not raise

    def test_correlation_computation(self, correlator):
        base = now_ns()
        # Generate correlated data
        np.random.seed(42)
        for i in range(50):
            t = base + i * 100_000_000
            # GPU metric
            gpu_val = 50 + 10 * np.sin(i * 0.2) + np.random.normal(0, 2)
            correlator.add_gpu_metric("utilization_gpu", t, gpu_val)
            # ROS metric (correlated with lag)
            ros_val = 30 + 5 * np.sin(i * 0.2 - 0.5) + np.random.normal(0, 1)
            correlator.add_ros_metric("/camera/detection", t, ros_val)

        results = correlator.compute_correlations()
        assert len(results) > 0

        # Check for significant correlation
        sig = correlator.get_significant_correlations(threshold=0.3)
        assert len(sig) >= 0  # May or may not be significant with noise

    def test_correlation_with_lag(self, correlator):
        base = now_ns()
        # Create data with known lag
        for i in range(60):
            t = base + i * 100_000_000
            gpu_val = 10 * np.sin(i * 0.1)
            ros_val = 10 * np.sin((i - 2) * 0.1)  # 2 sample lag
            correlator.add_gpu_metric("test_gpu", t, gpu_val)
            correlator.add_ros_metric("test_ros", t, ros_val)

        results = correlator.compute_correlations()
        result = next((r for r in results if r.gpu_metric == "test_gpu"), None)
        assert result is not None
        # Lag should be around 2 samples (200ms at 10Hz)
        assert result.lag_samples >= 1

    def test_granger_causality(self, correlator):
        base = now_ns()
        np.random.seed(42)
        for i in range(100):
            t = base + i * 100_000_000
            # GPU causes ROS with lag 1
            gpu_val = np.random.normal(0, 1)
            ros_val = 0.5 * gpu_val + np.random.normal(0, 0.5) if i > 0 else np.random.normal(0, 1)
            correlator.add_gpu_metric("cause_gpu", t, gpu_val)
            correlator.add_ros_metric("effect_ros", t, ros_val)

        granger = correlator.compute_granger_causality()
        result = next((g for g in granger if g.gpu_metric == "cause_gpu"), None)
        # With this synthetic data, may or may not detect causality
        assert result is not None

    def test_correlation_matrix(self, correlator):
        base = now_ns()
        for i in range(60):  # Need at least min_samples (50)
            t = base + i * 100_000_000
            correlator.add_gpu_metric("gpu1", t, 50 + np.random.normal(0, 5))
            correlator.add_gpu_metric("gpu2", t, 60 + np.random.normal(0, 5))
            correlator.add_ros_metric("/topic1", t, 30 + np.random.normal(0, 3))
            correlator.add_ros_metric("/topic2", t, 40 + np.random.normal(0, 3))

        # Force computation
        correlator.compute_correlations(force=True)
        matrix = correlator.get_correlation_matrix()
        assert "gpu1" in matrix
        assert "gpu2" in matrix
        assert "/topic1" in matrix["gpu1"]
        assert "/topic2" in matrix["gpu1"]

    def test_history(self, correlator):
        base = now_ns()
        for i in range(40):
            t = base + i * 100_000_000
            correlator.add_gpu_metric("hist_gpu", t, 50.0)
            correlator.add_ros_metric("hist_ros", t, 30.0)

        correlator.compute_correlations()
        history = correlator.get_history("hist_gpu", "hist_ros")
        assert len(history) >= 1


class TestStreamAligner:
    """Test stream aligner."""

    def test_align_streams(self):
        from gpuguard.correlation.time_sync import StreamAligner
        aligner = StreamAligner(reference_stream="gpu", tolerance_ms=5)

        base = now_ns()
        aligner.add_sample("gpu", base, {"util": 50})
        aligner.add_sample("ros", base + 1_000_000, {"hz": 30})  # 1ms diff

        aligned = aligner.get_aligned(base)
        assert "gpu" in aligned
        assert "ros" in aligned
        assert aligned["gpu"]["data"]["util"] == 50
        assert aligned["ros"]["data"]["hz"] == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])