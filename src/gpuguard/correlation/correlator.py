"""GPU-ROS 2 correlation engine."""
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy import stats, signal
from statsmodels.tsa.stattools import grangercausalitytests

from gpuguard.correlation.time_sync import TimeSynchronizer, SyncSample
from gpuguard.utils.config import get_config, CorrelationConfig
from gpuguard.utils.logging import get_logger
from gpuguard.utils.time_utils import now_ns

logger = get_logger("correlation.correlator")


@dataclass
class CorrelationResult:
    """Result of correlation analysis."""
    gpu_metric: str
    ros_topic: str
    correlation: float
    p_value: float
    lag_samples: int
    lag_ms: float
    method: str
    sample_count: int
    timestamp_ns: int
    significant: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gpu_metric": self.gpu_metric,
            "ros_topic": self.ros_topic,
            "correlation": self.correlation,
            "p_value": self.p_value,
            "lag_samples": self.lag_samples,
            "lag_ms": self.lag_ms,
            "method": self.method,
            "sample_count": self.sample_count,
            "timestamp_ns": self.timestamp_ns,
            "significant": self.significant,
        }


@dataclass
class GrangerResult:
    """Result of Granger causality test."""
    gpu_metric: str
    ros_topic: str
    causes_ros: bool
    p_value: float
    f_statistic: float
    optimal_lag: int
    sample_count: int
    timestamp_ns: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gpu_metric": self.gpu_metric,
            "ros_topic": self.ros_topic,
            "causes_ros": self.causes_ros,
            "p_value": self.p_value,
            "f_statistic": self.f_statistic,
            "optimal_lag": self.optimal_lag,
            "sample_count": self.sample_count,
            "timestamp_ns": self.timestamp_ns,
        }


class Correlator:
    """Compute correlations between GPU metrics and ROS 2 topic performance."""

    def __init__(self, config: Optional[CorrelationConfig] = None):
        self.config = config or get_config().correlation
        self.sync = TimeSynchronizer(
            tolerance_ms=self.config.sync_tolerance_ms,
            max_samples=self.config.rolling_window * 2,
        )

        # Correlation history
        self._correlation_history: Dict[str, List[CorrelationResult]] = defaultdict(list)
        self._granger_history: Dict[str, List[GrangerResult]] = defaultdict(list)

        # Rolling data buffers
        self._gpu_data: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
        self._ros_data: Dict[str, List[Tuple[int, float]]] = defaultdict(list)

        # Lock
        self._lock = threading.RLock()

        # Register sync callback
        self.sync.register_callback(self._on_sync_pair)

        # Last computation time
        self._last_compute_ns = 0

    def _on_sync_pair(self, pair: SyncSample) -> None:
        """Handle synchronized sample pair."""
        with self._lock:
            # Store in rolling buffers with actual values
            self._gpu_data[pair.gpu_metric].append((pair.gpu_timestamp_ns, pair.gpu_value))
            self._ros_data[pair.ros_topic].append((pair.ros_timestamp_ns, pair.ros_value))

            # Trim buffers
            max_len = self.config.rolling_window * 2
            for key in self._gpu_data:
                if len(self._gpu_data[key]) > max_len:
                    self._gpu_data[key] = self._gpu_data[key][-max_len:]
            for key in self._ros_data:
                if len(self._ros_data[key]) > max_len:
                    self._ros_data[key] = self._ros_data[key][-max_len:]

    def add_gpu_metric(self, metric: str, timestamp_ns: int, value: float) -> None:
        """Add GPU metric sample."""
        self.sync.add_gpu_sample(metric, timestamp_ns, value)

    def add_ros_metric(self, topic: str, timestamp_ns: int, value: float) -> None:
        """Add ROS metric sample (e.g., latency, Hz)."""
        self.sync.add_ros_sample(topic, timestamp_ns, value)

    def compute_correlations(self, force: bool = False) -> List[CorrelationResult]:
        """Compute correlations between all GPU metrics and ROS topics."""
        with self._lock:
            now = now_ns()

            # Throttle computation
            if not force and now - self._last_compute_ns < 1_000_000_000:  # 1 second
                return self._get_latest_correlations()

            self._last_compute_ns = now
            results = []

            # Get all metric/topic pairs
            gpu_metrics = list(self._gpu_data.keys())
            ros_topics = list(self._ros_data.keys())

            for gpu_metric in gpu_metrics:
                for ros_topic in ros_topics:
                    result = self._compute_pair_correlation(gpu_metric, ros_topic, now)
                    if result:
                        results.append(result)
                        self._correlation_history[f"{gpu_metric}|{ros_topic}"].append(result)

            # Trim history
            for key in self._correlation_history:
                if len(self._correlation_history[key]) > 1000:
                    self._correlation_history[key] = self._correlation_history[key][-1000:]

            return results

    def _compute_pair_correlation(self, gpu_metric: str, ros_topic: str,
                                   timestamp_ns: int) -> Optional[CorrelationResult]:
        """Compute correlation for a single metric-topic pair."""
        gpu_samples = self._gpu_data.get(gpu_metric, [])
        ros_samples = self._ros_data.get(ros_topic, [])

        if len(gpu_samples) < self.config.min_samples or len(ros_samples) < self.config.min_samples:
            return None

        # Align time series
        gpu_times = np.array([s[0] for s in gpu_samples])
        gpu_values = np.array([s[1] for s in gpu_samples])
        ros_times = np.array([s[0] for s in ros_samples])
        ros_values = np.array([s[1] for s in ros_samples])

        # Interpolate to common time base
        common_times = np.linspace(max(gpu_times[0], ros_times[0]),
                                   min(gpu_times[-1], ros_times[-1]),
                                   min(len(gpu_times), len(ros_times)))

        if len(common_times) < self.config.min_samples:
            return None

        gpu_interp = np.interp(common_times, gpu_times, gpu_values)
        ros_interp = np.interp(common_times, ros_times, ros_values)

        # Compute correlation with lag
        max_lag = min(self.config.granger_maxlag, len(common_times) // 4)
        best_corr = 0.0
        best_lag = 0
        best_p = 1.0

        for lag in range(-max_lag, max_lag + 1):
            if lag < 0:
                gpu_lagged = gpu_interp[-lag:]
                ros_lagged = ros_interp[:lag]
            elif lag > 0:
                gpu_lagged = gpu_interp[:-lag]
                ros_lagged = ros_interp[lag:]
            else:
                gpu_lagged = gpu_interp
                ros_lagged = ros_interp

            if len(gpu_lagged) < 10:
                continue

            try:
                if self.config.correlation_method == "pearson":
                    corr, p = stats.pearsonr(gpu_lagged, ros_lagged)
                elif self.config.correlation_method == "spearman":
                    corr, p = stats.spearmanr(gpu_lagged, ros_lagged)
                else:
                    corr, p = stats.kendalltau(gpu_lagged, ros_lagged)

                if abs(corr) > abs(best_corr):
                    best_corr = corr
                    best_lag = lag
                    best_p = p
            except Exception:
                continue

        # Convert lag to milliseconds
        if len(common_times) > 1:
            sample_interval_ms = (common_times[1] - common_times[0]) / 1_000_000.0
            lag_ms = best_lag * sample_interval_ms
        else:
            lag_ms = 0.0

        significant = best_p < self.config.significance_level

        return CorrelationResult(
            gpu_metric=gpu_metric,
            ros_topic=ros_topic,
            correlation=best_corr,
            p_value=best_p,
            lag_samples=best_lag,
            lag_ms=lag_ms,
            method=self.config.correlation_method,
            sample_count=len(common_times),
            timestamp_ns=timestamp_ns,
            significant=significant,
        )

    def compute_granger_causality(self) -> List[GrangerResult]:
        """Test Granger causality: does GPU metric cause ROS topic changes?"""
        with self._lock:
            now = now_ns()
            results = []

            gpu_metrics = list(self._gpu_data.keys())
            ros_topics = list(self._ros_data.keys())

            for gpu_metric in gpu_metrics:
                for ros_topic in ros_topics:
                    result = self._compute_granger(gpu_metric, ros_topic, now)
                    if result:
                        results.append(result)
                        self._granger_history[f"{gpu_metric}|{ros_topic}"].append(result)

            # Trim history
            for key in self._granger_history:
                if len(self._granger_history[key]) > 500:
                    self._granger_history[key] = self._granger_history[key][-500:]

            return results

    def _compute_granger(self, gpu_metric: str, ros_topic: str,
                          timestamp_ns: int) -> Optional[GrangerResult]:
        """Compute Granger causality for a pair."""
        gpu_samples = self._gpu_data.get(gpu_metric, [])
        ros_samples = self._ros_data.get(ros_topic, [])

        min_samples = max(self.config.min_samples, self.config.granger_maxlag * 10)
        if len(gpu_samples) < min_samples or len(ros_samples) < min_samples:
            return None

        # Align and interpolate
        gpu_times = np.array([s[0] for s in gpu_samples])
        gpu_values = np.array([s[1] for s in gpu_samples])
        ros_times = np.array([s[0] for s in ros_samples])
        ros_values = np.array([s[1] for s in ros_samples])

        common_times = np.linspace(max(gpu_times[0], ros_times[0]),
                                   min(gpu_times[-1], ros_times[-1]),
                                   min(len(gpu_times), len(ros_times)))

        if len(common_times) < min_samples:
            return None

        gpu_interp = np.interp(common_times, gpu_times, gpu_values)
        ros_interp = np.interp(common_times, ros_times, ros_values)

        # Prepare data for Granger test (ros ~ gpu + lagged ros)
        # We test if GPU metric helps predict ROS topic
        try:
            # Create lagged dataset
            data = pd.DataFrame({
                'ros': ros_interp,
                'gpu': gpu_interp,
            })

            # Test different lags
            best_p = 1.0
            best_f = 0.0
            best_lag = 1

            for lag in range(1, self.config.granger_maxlag + 1):
                if len(data) <= lag + 5:
                    break

                # Create lagged variables
                test_data = pd.DataFrame()
                test_data['ros'] = data['ros'].iloc[lag:].values
                test_data['ros_lag'] = data['ros'].iloc[:-lag].values
                test_data['gpu_lag'] = data['gpu'].iloc[:-lag].values

                # Run Granger test
                try:
                    gc_result = grangercausalitytests(
                        test_data[['ros', 'gpu_lag']].values,
                        maxlag=1,
                        verbose=False
                    )
                    p_val = gc_result[1][0]['ssr_ftest'][1]
                    f_stat = gc_result[1][0]['ssr_ftest'][0]

                    if p_val < best_p:
                        best_p = p_val
                        best_f = f_stat
                        best_lag = lag
                except Exception:
                    continue

            causes_ros = best_p < self.config.significance_level

            return GrangerResult(
                gpu_metric=gpu_metric,
                ros_topic=ros_topic,
                causes_ros=causes_ros,
                p_value=best_p,
                f_statistic=best_f,
                optimal_lag=best_lag,
                sample_count=len(common_times),
                timestamp_ns=timestamp_ns,
            )
        except Exception as e:
            logger.debug(f"Granger test failed for {gpu_metric} -> {ros_topic}: {e}")
            return None

    def _get_latest_correlations(self) -> List[CorrelationResult]:
        """Get latest correlation results."""
        results = []
        for key, history in self._correlation_history.items():
            if history:
                results.append(history[-1])
        return results

    def get_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Get correlation matrix as nested dict."""
        with self._lock:
            latest = self._get_latest_correlations()
            matrix = defaultdict(dict)

            for result in latest:
                matrix[result.gpu_metric][result.ros_topic] = result.correlation

            return dict(matrix)

    def get_significant_correlations(self, threshold: float = 0.5) -> List[CorrelationResult]:
        """Get statistically significant correlations above threshold."""
        with self._lock:
            latest = self._get_latest_correlations()
            return [r for r in latest if r.significant and abs(r.correlation) >= threshold]

    def get_granger_causality(self) -> List[GrangerResult]:
        """Get latest Granger causality results."""
        with self._lock:
            results = []
            for key, history in self._granger_history.items():
                if history:
                    results.append(history[-1])
            return results

    def get_history(self, gpu_metric: str, ros_topic: str) -> List[CorrelationResult]:
        """Get correlation history for a pair."""
        key = f"{gpu_metric}|{ros_topic}"
        return self._correlation_history.get(key, [])

    def clear(self) -> None:
        """Clear all data."""
        with self._lock:
            self._gpu_data.clear()
            self._ros_data.clear()
            self._correlation_history.clear()
            self._granger_history.clear()
            self.sync.clear()