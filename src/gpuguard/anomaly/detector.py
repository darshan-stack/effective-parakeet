"""Anomaly detection for GPU and ROS 2 metrics."""
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import deque
from enum import Enum
import time
import numpy as np
from sklearn.ensemble import IsolationForest

from gpuguard.utils.config import get_config, AnomalyConfig
from gpuguard.utils.logging import get_logger

logger = get_logger("anomaly.detector")


class AnomalyType(str, Enum):
    """Types of anomalies."""
    VRAM_PRESSURE = "vram"
    THERMAL_THROTTLING = "thermal"
    CLOCK_DROP = "clock"
    POWER_THROTTLE = "power"
    ECC_ERRORS = "ecc"
    LATENCY_SPIKE = "latency"
    HZ_DROP = "hz_drop"
    DEADLINE_MISS = "deadline"
    ISOLATION_FOREST = "isolation_forest"


class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """Detected anomaly."""
    timestamp_ns: int
    type: AnomalyType
    severity: AnomalySeverity
    gpu_metric: str = ""
    ros_topic: str = ""
    message: str = ""
    value: float = 0.0
    threshold: float = 0.0
    gpu_id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp_ns / 1e9,
            "type": self.type.value,
            "severity": self.severity.value,
            "gpu_metric": self.gpu_metric,
            "ros_topic": self.ros_topic,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "gpu_id": self.gpu_id,
        }


class AnomalyDetector:
    """Detects anomalies in GPU and ROS 2 metrics."""

    def __init__(self, config: Optional[AnomalyConfig] = None):
        self.config = config or get_config().anomaly
        self._lock = threading.RLock()

        # Anomaly history
        self._anomalies: deque = deque(maxlen=10000)

        # Baseline tracking for statistical detection
        self._gpu_baselines: Dict[int, Dict[str, deque]] = {}
        self._topic_baselines: Dict[str, Dict[str, deque]] = {}

        # Isolation Forest for ML-based detection
        self._iso_forest: Optional[IsolationForest] = None
        self._iso_trained = False
        self._training_data: List[List[float]] = []

        # GPU state cache
        self._last_gpu_state: Dict[int, Dict] = {}
        self._last_topic_stats: Dict[str, Dict] = {}

    def check_gpu(self, gpu_id: int, metrics: Dict[str, float]) -> List[Anomaly]:
        """Check GPU metrics for anomalies."""
        anomalies = []

        with self._lock:
            # Cache state
            self._last_gpu_state[gpu_id] = metrics

            # Initialize baselines
            if gpu_id not in self._gpu_baselines:
                self._gpu_baselines[gpu_id] = {
                    "memory_used_pct": deque(maxlen=100),
                    "temperature_gpu": deque(maxlen=100),
                    "utilization_gpu": deque(maxlen=100),
                    "power_draw_pct": deque(maxlen=100),
                    "clock_graphics": deque(maxlen=100),
                }

            baselines = self._gpu_baselines[gpu_id]
            timestamp = time.time_ns()

            # Update baselines
            for key, value in metrics.items():
                if key in baselines:
                    baselines[key].append(value)

            # Statistical threshold checks
            anomalies.extend(self._check_gpu_thresholds(gpu_id, metrics, timestamp))

            # Isolation Forest anomaly detection
            if self.config.isolation_forest_contamination > 0:
                anomalies.extend(self._check_isolation_forest(gpu_id, metrics, timestamp))

            # Store anomalies
            for a in anomalies:
                self._anomalies.append(a)

        return anomalies

    def _check_gpu_thresholds(self, gpu_id: int, metrics: Dict, timestamp: int) -> List[Anomaly]:
        """Check GPU metrics against configured thresholds."""
        anomalies = []

        # VRAM pressure
        vram_pct = metrics.get("memory_used_pct", 0)
        if vram_pct >= self.config.vram_threshold_pct:
            severity = AnomalySeverity.CRITICAL if vram_pct >= 95 else AnomalySeverity.WARNING
            anomalies.append(Anomaly(
                timestamp_ns=timestamp,
                type=AnomalyType.VRAM_PRESSURE,
                severity=severity,
                gpu_metric="memory_used_pct",
                message=f"GPU {gpu_id} VRAM usage at {vram_pct:.1f}%",
                value=vram_pct,
                threshold=self.config.vram_threshold_pct,
                gpu_id=gpu_id,
            ))

        # Thermal throttling
        temp = metrics.get("temperature_gpu", 0)
        if temp >= self.config.temp_critical_c:
            anomalies.append(Anomaly(
                timestamp_ns=timestamp,
                type=AnomalyType.THERMAL_THROTTLING,
                severity=AnomalySeverity.CRITICAL,
                gpu_metric="temperature_gpu",
                message=f"GPU {gpu_id} critical temperature: {temp:.1f}°C",
                value=temp,
                threshold=self.config.temp_critical_c,
                gpu_id=gpu_id,
            ))
        elif temp >= self.config.temp_threshold_c:
            anomalies.append(Anomaly(
                timestamp_ns=timestamp,
                type=AnomalyType.THERMAL_THROTTLING,
                severity=AnomalySeverity.WARNING,
                gpu_metric="temperature_gpu",
                message=f"GPU {gpu_id} high temperature: {temp:.1f}°C",
                value=temp,
                threshold=self.config.temp_threshold_c,
                gpu_id=gpu_id,
            ))

        # Clock drop detection (requires baseline)
        clock = metrics.get("clock_graphics", 0)
        clock_baseline = self._gpu_baselines[gpu_id].get("clock_graphics", deque())
        if clock > 0 and len(clock_baseline) > 10:
            baseline_avg = np.mean(list(clock_baseline)[:-1])  # Exclude current
            if baseline_avg > 0:
                drop_pct = (baseline_avg - clock) / baseline_avg * 100
                if drop_pct >= self.config.clock_drop_threshold_pct:
                    anomalies.append(Anomaly(
                        timestamp_ns=timestamp,
                        type=AnomalyType.CLOCK_DROP,
                        severity=AnomalySeverity.WARNING,
                        gpu_metric="clock_graphics",
                        message=f"GPU {gpu_id} clock dropped {drop_pct:.1f}% from baseline",
                        value=clock,
                        threshold=baseline_avg * (1 - self.config.clock_drop_threshold_pct / 100),
                        gpu_id=gpu_id,
                    ))

        # Power throttle
        power_pct = metrics.get("power_draw_pct", 0)
        if power_pct >= self.config.power_throttle_threshold_pct:
            anomalies.append(Anomaly(
                timestamp_ns=timestamp,
                type=AnomalyType.POWER_THROTTLE,
                severity=AnomalySeverity.WARNING,
                gpu_metric="power_draw_pct",
                message=f"GPU {gpu_id} power limit throttle: {power_pct:.1f}%",
                value=power_pct,
                threshold=self.config.power_throttle_threshold_pct,
                gpu_id=gpu_id,
            ))

        # ECC errors
        ecc = metrics.get("ecc_errors_volatile", 0)
        if ecc > self.config.ecc_error_threshold:
            anomalies.append(Anomaly(
                timestamp_ns=timestamp,
                type=AnomalyType.ECC_ERRORS,
                severity=AnomalySeverity.CRITICAL,
                gpu_metric="ecc_errors_volatile",
                message=f"GPU {gpu_id} ECC errors detected: {ecc}",
                value=float(ecc),
                threshold=float(self.config.ecc_error_threshold),
                gpu_id=gpu_id,
            ))

        # Throttling flag
        if metrics.get("is_throttling", False):
            anomalies.append(Anomaly(
                timestamp_ns=timestamp,
                type=AnomalyType.THERMAL_THROTTLING,
                severity=AnomalySeverity.WARNING,
                gpu_metric="performance_state",
                message=f"GPU {gpu_id} throttling detected via performance state",
                value=1.0,
                threshold=0.0,
                gpu_id=gpu_id,
            ))

        return anomalies

    def _check_isolation_forest(self, gpu_id: int, metrics: Dict, timestamp: int) -> List[Anomaly]:
        """Check for anomalies using Isolation Forest."""
        anomalies = []

        # Prepare feature vector
        features = [
            metrics.get("memory_used_pct", 0),
            metrics.get("temperature_gpu", 0),
            metrics.get("utilization_gpu", 0),
            metrics.get("power_draw_pct", 0),
            metrics.get("clock_graphics", 0) / 1000.0,  # Normalize
            metrics.get("fan_speed", 0),
        ]

        # Add to training data
        self._training_data.append(features)

        # Train periodically
        if len(self._training_data) >= 100 and not self._iso_trained:
            self._train_isolation_forest()
        elif len(self._training_data) % 500 == 0:
            self._train_isolation_forest()

        # Predict
        if self._iso_forest is not None and self._iso_trained:
            try:
                score = self._iso_forest.score_samples([features])[0]
                prediction = self._iso_forest.predict([features])[0]

                # Isolation Forest: -1 = anomaly, 1 = normal
                if prediction == -1:
                    anomalies.append(Anomaly(
                        timestamp_ns=timestamp,
                        type=AnomalyType.ISOLATION_FOREST,
                        severity=AnomalySeverity.WARNING,
                        gpu_metric="multi",
                        message=f"GPU {gpu_id} anomalous behavior detected (score: {score:.3f})",
                        value=score,
                        threshold=0.0,
                        gpu_id=gpu_id,
                    ))
            except Exception as e:
                logger.debug(f"Isolation Forest prediction failed: {e}")

        return anomalies

    def _train_isolation_forest(self) -> None:
        """Train Isolation Forest model."""
        if len(self._training_data) < 50:
            return

        try:
            X = np.array(self._training_data[-1000:])  # Use recent data
            self._iso_forest = IsolationForest(
                contamination=self.config.isolation_forest_contamination,
                n_estimators=self.config.isolation_forest_n_estimators,
                random_state=42,
                n_jobs=1,
            )
            self._iso_forest.fit(X)
            self._iso_trained = True
            logger.info(f"Isolation Forest trained on {len(X)} samples")
        except Exception as e:
            logger.warning(f"Isolation Forest training failed: {e}")

    def check_topic(self, topic: str, stats: Dict[str, float]) -> List[Anomaly]:
        """Check ROS topic statistics for anomalies."""
        anomalies = []

        with self._lock:
            self._last_topic_stats[topic] = stats
            timestamp = time.time_ns()

            # Initialize baselines
            if topic not in self._topic_baselines:
                self._topic_baselines[topic] = {
                    "current_hz": deque(maxlen=100),
                    "avg_latency_ms": deque(maxlen=100),
                    "p99_latency_ms": deque(maxlen=100),
                }

            baselines = self._topic_baselines[topic]

            # Update baselines
            for key, value in stats.items():
                if key in baselines:
                    baselines[key].append(value)

            # Latency spike
            avg_lat = stats.get("avg_latency_ms", 0)
            p99_lat = stats.get("p99_latency_ms", 0)
            if avg_lat > 0 and p99_lat > avg_lat * self.config.latency_spike_threshold:
                anomalies.append(Anomaly(
                    timestamp_ns=timestamp,
                    type=AnomalyType.LATENCY_SPIKE,
                    severity=AnomalySeverity.WARNING,
                    ros_topic=topic,
                    message=f"Topic {topic} latency spike: P99={p99_lat:.1f}ms (avg={avg_lat:.1f}ms)",
                    value=p99_lat,
                    threshold=avg_lat * self.config.latency_spike_threshold,
                ))

            # Hz drop
            current_hz = stats.get("current_hz", 0)
            deadline_ms = stats.get("deadline_ms", 50)
            expected_hz = 1000.0 / deadline_ms if deadline_ms > 0 else 0
            if expected_hz > 0 and current_hz < expected_hz * (1 - self.config.hz_drop_threshold_pct / 100):
                anomalies.append(Anomaly(
                    timestamp_ns=timestamp,
                    type=AnomalyType.HZ_DROP,
                    severity=AnomalySeverity.WARNING,
                    ros_topic=topic,
                    message=f"Topic {topic} rate dropped: {current_hz:.1f}Hz (expected {expected_hz:.1f}Hz)",
                    value=current_hz,
                    threshold=expected_hz * (1 - self.config.hz_drop_threshold_pct / 100),
                ))

            # Deadline misses
            consecutive = stats.get("consecutive_misses", 0)
            if consecutive >= self.config.deadline_miss_threshold:
                severity = AnomalySeverity.CRITICAL if consecutive > 5 else AnomalySeverity.WARNING
                anomalies.append(Anomaly(
                    timestamp_ns=timestamp,
                    type=AnomalyType.DEADLINE_MISS,
                    severity=severity,
                    ros_topic=topic,
                    message=f"Topic {topic} missed {consecutive} consecutive deadlines",
                    value=float(consecutive),
                    threshold=float(self.config.deadline_miss_threshold),
                ))

            # Store anomalies
            for a in anomalies:
                self._anomalies.append(a)

        return anomalies

    def get_recent_anomalies(self, max_age_s: float = 60.0) -> List[Anomaly]:
        """Get recent anomalies within time window."""
        with self._lock:
            now = time.time_ns()
            cutoff = now - int(max_age_s * 1e9)
            return [a for a in self._anomalies if a.timestamp_ns >= cutoff]

    def get_all_anomalies(self) -> List[Anomaly]:
        """Get all anomalies."""
        with self._lock:
            return list(self._anomalies)

    def clear_anomalies(self) -> None:
        """Clear anomaly history."""
        with self._lock:
            self._anomalies.clear()

    def get_anomaly_summary(self) -> Dict[str, int]:
        """Get anomaly count by type."""
        with self._lock:
            summary = {}
            for a in self._anomalies:
                key = a.type.value
                summary[key] = summary.get(key, 0) + 1
            return summary