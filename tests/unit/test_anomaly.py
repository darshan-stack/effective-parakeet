"""Unit tests for anomaly detection."""
import pytest
import time
import numpy as np
from unittest.mock import Mock, patch

from gpuguard.anomaly.detector import AnomalyDetector, Anomaly, AnomalyType, AnomalySeverity
from gpuguard.utils.config import AnomalyConfig


class TestAnomalyDetector:
    """Test anomaly detector."""

    @pytest.fixture
    def config(self):
        return AnomalyConfig(
            vram_threshold_pct=85.0,
            temp_threshold_c=80.0,
            temp_critical_c=85.0,
            clock_drop_threshold_pct=15.0,
            power_throttle_threshold_pct=90.0,
            latency_spike_threshold=3.0,
            hz_drop_threshold_pct=30.0,
            deadline_miss_threshold=3,
            ecc_error_threshold=0,
            isolation_forest_contamination=0.05,
            isolation_forest_n_estimators=100,
        )

    @pytest.fixture
    def detector(self, config):
        return AnomalyDetector(config)

    def test_vram_pressure_detection(self, detector):
        """Test VRAM pressure anomaly detection."""
        metrics = {
            "memory_used_pct": 90.0,
            "temperature_gpu": 65.0,
            "utilization_gpu": 50.0,
            "power_draw_pct": 50.0,
            "clock_graphics": 2000,
            "ecc_errors_volatile": 0,
            "is_throttling": False,
        }

        anomalies = detector.check_gpu(0, metrics)
        vram_anomalies = [a for a in anomalies if a.type == AnomalyType.VRAM_PRESSURE]
        assert len(vram_anomalies) == 1
        assert vram_anomalies[0].severity == AnomalySeverity.WARNING
        assert vram_anomalies[0].value == 90.0

    def test_vram_critical(self, detector):
        """Test critical VRAM pressure."""
        metrics = {
            "memory_used_pct": 98.0,
            "temperature_gpu": 65.0,
            "utilization_gpu": 50.0,
            "power_draw_pct": 50.0,
            "clock_graphics": 2000,
            "ecc_errors_volatile": 0,
            "is_throttling": False,
        }

        anomalies = detector.check_gpu(0, metrics)
        vram_anomalies = [a for a in anomalies if a.type == AnomalyType.VRAM_PRESSURE]
        assert len(vram_anomalies) == 1
        assert vram_anomalies[0].severity == AnomalySeverity.CRITICAL

    def test_thermal_throttling(self, detector):
        """Test thermal throttling detection."""
        metrics = {
            "memory_used_pct": 50.0,
            "temperature_gpu": 88.0,
            "utilization_gpu": 80.0,
            "power_draw_pct": 80.0,
            "clock_graphics": 1500,
            "ecc_errors_volatile": 0,
            "is_throttling": True,
        }

        anomalies = detector.check_gpu(0, metrics)
        thermal = [a for a in anomalies if a.type == AnomalyType.THERMAL_THROTTLING]
        assert len(thermal) >= 1
        assert any(a.severity == AnomalySeverity.CRITICAL for a in thermal)

    def test_high_temperature_warning(self, detector):
        """Test high temperature warning."""
        metrics = {
            "memory_used_pct": 50.0,
            "temperature_gpu": 82.0,
            "utilization_gpu": 80.0,
            "power_draw_pct": 80.0,
            "clock_graphics": 2000,
            "ecc_errors_volatile": 0,
            "is_throttling": False,
        }

        anomalies = detector.check_gpu(0, metrics)
        thermal = [a for a in anomalies if a.type == AnomalyType.THERMAL_THROTTLING]
        assert len(thermal) >= 1
        assert any(a.severity == AnomalySeverity.WARNING for a in thermal)

    def test_clock_drop_detection(self, detector):
        """Test clock drop detection."""
        # Establish baseline
        for i in range(15):
            detector.check_gpu(0, {
                "memory_used_pct": 50.0,
                "temperature_gpu": 65.0,
                "utilization_gpu": 50.0,
                "power_draw_pct": 50.0,
                "clock_graphics": 2000,
                "ecc_errors_volatile": 0,
                "is_throttling": False,
            })

        # Now drop clock
        metrics = {
            "memory_used_pct": 50.0,
            "temperature_gpu": 65.0,
            "utilization_gpu": 50.0,
            "power_draw_pct": 50.0,
            "clock_graphics": 1500,  # 25% drop
            "ecc_errors_volatile": 0,
            "is_throttling": False,
        }

        anomalies = detector.check_gpu(0, metrics)
        clock_anomalies = [a for a in anomalies if a.type == AnomalyType.CLOCK_DROP]
        assert len(clock_anomalies) == 1
        assert clock_anomalies[0].value == 1500

    def test_power_throttle_detection(self, detector):
        """Test power throttle detection."""
        metrics = {
            "memory_used_pct": 50.0,
            "temperature_gpu": 70.0,
            "utilization_gpu": 95.0,
            "power_draw_pct": 95.0,
            "clock_graphics": 2000,
            "ecc_errors_volatile": 0,
            "is_throttling": False,
        }

        anomalies = detector.check_gpu(0, metrics)
        power = [a for a in anomalies if a.type == AnomalyType.POWER_THROTTLE]
        assert len(power) == 1
        assert power[0].severity == AnomalySeverity.WARNING

    def test_ecc_error_detection(self, detector):
        """Test ECC error detection."""
        metrics = {
            "memory_used_pct": 50.0,
            "temperature_gpu": 65.0,
            "utilization_gpu": 50.0,
            "power_draw_pct": 50.0,
            "clock_graphics": 2000,
            "ecc_errors_volatile": 5,
            "is_throttling": False,
        }

        anomalies = detector.check_gpu(0, metrics)
        ecc = [a for a in anomalies if a.type == AnomalyType.ECC_ERRORS]
        assert len(ecc) == 1
        assert ecc[0].severity == AnomalySeverity.CRITICAL

    def test_latency_spike_detection(self, detector):
        """Test topic latency spike detection."""
        stats = {
            "avg_latency_ms": 10.0,
            "p99_latency_ms": 50.0,  # 5x spike
            "current_hz": 30.0,
            "deadline_ms": 33.0,
            "consecutive_misses": 0,
        }

        anomalies = detector.check_topic("/camera/detection", stats)
        latency = [a for a in anomalies if a.type == AnomalyType.LATENCY_SPIKE]
        assert len(latency) == 1
        assert latency[0].value == 50.0
        assert latency[0].threshold == 30.0  # 10 * 3.0

    def test_hz_drop_detection(self, detector):
        """Test topic Hz drop detection."""
        stats = {
            "avg_latency_ms": 10.0,
            "p99_latency_ms": 15.0,
            "current_hz": 20.0,  # Below 70% of expected
            "deadline_ms": 33.0,  # Expected ~30Hz
            "consecutive_misses": 0,
        }

        anomalies = detector.check_topic("/scan", stats)
        hz_drop = [a for a in anomalies if a.type == AnomalyType.HZ_DROP]
        assert len(hz_drop) == 1

    def test_deadline_miss_detection(self, detector):
        """Test consecutive deadline miss detection."""
        stats = {
            "avg_latency_ms": 10.0,
            "p99_latency_ms": 15.0,
            "current_hz": 30.0,
            "deadline_ms": 33.0,
            "consecutive_misses": 5,  # Above threshold of 3
        }

        anomalies = detector.check_topic("/cmd_vel", stats)
        deadline = [a for a in anomalies if a.type == AnomalyType.DEADLINE_MISS]
        assert len(deadline) == 1
        assert deadline[0].severity == AnomalySeverity.CRITICAL

    def test_get_recent_anomalies(self, detector):
        """Test getting recent anomalies."""
        # Add some anomalies
        for i in range(5):
            detector.check_gpu(0, {
                "memory_used_pct": 90.0,
                "temperature_gpu": 65.0,
                "utilization_gpu": 50.0,
                "power_draw_pct": 50.0,
                "clock_graphics": 2000,
                "ecc_errors_volatile": 0,
                "is_throttling": False,
            })

        recent = detector.get_recent_anomalies(max_age_s=60.0)
        assert len(recent) >= 5

    def test_anomaly_summary(self, detector):
        """Test anomaly summary."""
        detector.check_gpu(0, {
            "memory_used_pct": 90.0,
            "temperature_gpu": 88.0,
            "utilization_gpu": 50.0,
            "power_draw_pct": 50.0,
            "clock_graphics": 2000,
            "ecc_errors_volatile": 0,
            "is_throttling": False,
        })

        summary = detector.get_anomaly_summary()
        assert "vram" in summary
        assert "thermal" in summary

    def test_clear_anomalies(self, detector):
        """Test clearing anomalies."""
        detector.check_gpu(0, {
            "memory_used_pct": 90.0,
            "temperature_gpu": 65.0,
            "utilization_gpu": 50.0,
            "power_draw_pct": 50.0,
            "clock_graphics": 2000,
            "ecc_errors_volatile": 0,
            "is_throttling": False,
        })

        detector.clear_anomalies()
        assert len(detector.get_all_anomalies()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])