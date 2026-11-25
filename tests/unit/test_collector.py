"""Unit tests for GPU collector."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from gpuguard.collector.metrics import GPUState, GPUInfo, GPUMetric, DEFAULT_METRICS
from gpuguard.collector.nvml_collector import MockNVMLCollector, NVMLCollector
from gpuguard.collector.sampler import GPUSampler, MetricAggregator
from gpuguard.utils.config import CollectorConfig
from gpuguard.utils.time_utils import now_ns


class TestGPUMetrics:
    """Test GPU metric data structures."""

    def test_gpu_state_creation(self):
        """Test GPUState creation and derived fields."""
        state = GPUState(
            timestamp_ns=now_ns(),
            gpu_id=0,
            name="RTX 4090",
            memory_used=8_000_000_000,
            memory_total=24_000_000_000,
            utilization_gpu=75.0,
            temperature_gpu=65.0,
            power_draw=250.0,
            power_limit=450.0,
            clock_graphics=2500,
        )

        assert state.memory_used_pct == pytest.approx(33.33, rel=0.01)
        assert state.power_draw_pct == pytest.approx(55.56, rel=0.01)
        assert not state.is_throttling
        assert not state.vram_pressure

    def test_gpu_state_throttling(self):
        """Test throttling detection."""
        state = GPUState(
            timestamp_ns=now_ns(),
            gpu_id=0,
            temperature_gpu=85.0,
            power_draw_pct=95.0,
        )
        assert state.is_throttling

    def test_gpu_state_vram_pressure(self):
        """Test VRAM pressure detection."""
        state = GPUState(
            timestamp_ns=now_ns(),
            gpu_id=0,
            memory_used_pct=90.0,
        )
        assert state.vram_pressure

    def test_gpu_info_to_dict(self):
        """Test GPUInfo serialization."""
        info = GPUInfo(
            gpu_id=0,
            name="RTX 4090",
            uuid="GPU-xxx",
            driver_version="535.154.05",
            vram_total=24_000_000_000,
            compute_capability="8.9",
            pcie_gen=4,
            pcie_width=16,
            multiprocessors=128,
            cuda_cores=16384,
            tensor_cores=512,
            rt_cores=128,
        )
        d = info.to_dict()
        assert d["gpu_id"] == 0
        assert d["vram_total_gb"] == pytest.approx(24.0, rel=0.1)


class TestMockNVMLCollector:
    """Test mock NVML collector."""

    @pytest.fixture
    def config(self):
        return CollectorConfig(poll_interval_ms=100, gpu_indices=[0], buffer_size=1000)

    @pytest.fixture
    def collector(self, config):
        return MockNVMLCollector(config)

    def test_initialize(self, collector):
        assert collector.initialize()
        assert len(collector.get_all_gpu_infos()) == 1

    def test_sample_now(self, collector):
        collector.initialize()
        samples = collector.sample_now()
        assert 0 in samples
        state = samples[0]
        assert isinstance(state, GPUState)
        assert state.gpu_id == 0

    def test_callbacks(self, collector):
        collector.initialize()
        received = []

        def callback(state):
            received.append(state)

        collector.register_callback(callback)
        collector.start()

        import time
        time.sleep(0.3)  # Wait for a few samples

        collector.stop()
        assert len(received) > 0

    def test_mock_gpu_info(self, collector):
        collector.initialize()
        info = collector.get_gpu_info(0)
        assert info is not None
        assert info.name == "Mock GPU (RTX 4090)"
        assert info.vram_total == 8_000_000_000


class TestGPUSampler:
    """Test GPU sampler."""

    @pytest.fixture
    def sampler(self):
        return GPUSampler(buffer_size=100)

    def test_add_sample(self, sampler):
        state = GPUState(
            timestamp_ns=now_ns(),
            gpu_id=0,
            memory_used=4_000_000_000,
            memory_total=8_000_000_000,
            utilization_gpu=50.0,
        )
        sampler.add_sample(state)
        latest = sampler.get_latest(0)
        assert latest is not None
        assert latest.memory_used_pct == 50.0

    def test_history(self, sampler):
        for i in range(10):
            state = GPUState(
                timestamp_ns=now_ns() + i * 1_000_000_000,
                gpu_id=0,
                utilization_gpu=float(i * 10),
            )
            sampler.add_sample(state)

        history = sampler.get_history(0, max_samples=5)
        assert len(history) == 5
        assert history[-1].utilization_gpu == 90.0

    def test_window_stats(self, sampler):
        for i in range(20):
            state = GPUState(
                timestamp_ns=now_ns() + i * 1_000_000_000,
                gpu_id=0,
                memory_used_pct=50.0 + i,
            )
            sampler.add_sample(state)

        stats = sampler.get_window_stats(0)
        assert stats["count"] == 20
        assert stats["mean"] == pytest.approx(59.5, rel=0.1)
        assert stats["p50"] == pytest.approx(59.5, rel=0.1)


class TestMetricAggregator:
    """Test metric aggregator."""

    def test_aggregation(self):
        agg = MetricAggregator(window_s=10.0)
        base_time = now_ns()

        for i in range(100):
            state = GPUState(
                timestamp_ns=base_time + i * 100_000_000,
                gpu_id=0,
                memory_used_pct=50.0,
                utilization_gpu=60.0,
                temperature_gpu=65.0,
                power_draw=200.0,
                clock_graphics=2000,
                fan_speed=50.0,
            )
            agg.add(state)

        result = agg.get_aggregated(0)
        assert result["count"] == 100
        assert result["memory_used_pct_avg"] == 50.0
        assert result["utilization_gpu_avg"] == 60.0
        assert result["temperature_gpu_max"] == 65.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])