#!/usr/bin/env python3
"""GPUGuard Benchmark Suite.

Runs standardized benchmarks to validate GPUGuard functionality.
"""
import argparse
import json
import time
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

import torch
import numpy as np


@dataclass
class BenchmarkResult:
    name: str
    duration_s: float
    metrics: Dict[str, Any]
    success: bool
    error: str = ""


def benchmark_gpu_collection(duration: float = 10.0) -> BenchmarkResult:
    """Benchmark GPU telemetry collection."""
    print("Benchmarking GPU telemetry collection...")

    try:
        from gpuguard.collector.nvml_collector import NVMLCollector, MockNVMLCollector
        from gpuguard.collector.sampler import GPUSampler
        from gpuguard.utils.config import CollectorConfig

        config = CollectorConfig(poll_interval_ms=100, gpu_indices=[0], buffer_size=10000)

        # Use mock if no GPU
        if torch.cuda.is_available():
            collector = NVMLCollector(config)
        else:
            collector = MockNVMLCollector(config)

        sampler = GPUSampler(buffer_size=config.buffer_size)
        collector.register_callback(lambda s: sampler.add_sample(s))

        if not collector.initialize():
            return BenchmarkResult("gpu_collection", 0, {}, False, "Failed to initialize collector")

        collector.start()

        time.sleep(duration)

        collector.stop()

        stats = collector.get_stats()
        samp_stats = sampler.get_stats()

        return BenchmarkResult(
            "gpu_collection",
            duration,
            {
                "samples_collected": stats.samples_collected,
                "samples_failed": stats.samples_failed,
                "gpu_count": stats.gpu_count,
                "sampler_total": samp_stats.total_samples,
                "sampler_overflows": samp_stats.buffer_overflows,
                "target_hz": 1000 / config.poll_interval_ms,
                "actual_hz": stats.samples_collected / duration if duration > 0 else 0,
            },
            True,
        )
    except Exception as e:
        return BenchmarkResult("gpu_collection", duration, {}, False, str(e))


def benchmark_ros_monitoring(duration: float = 10.0) -> BenchmarkResult:
    """Benchmark ROS 2 topic monitoring."""
    print("Benchmarking ROS 2 topic monitoring...")

    try:
        import rclpy
        from gpuguard.monitor.ros_monitor import create_ros_monitor
        from gpuguard.monitor.topic_tracker import TopicTracker
        from gpuguard.utils.config import MonitorConfig

        rclpy.init()

        config = MonitorConfig(
            topics=["/test_topic_1", "/test_topic_2", "/test_topic_3"],
            deadline_ms=33,
            window_size=100,
        )

        monitor = create_ros_monitor(config)
        monitor.start_monitoring()

        # Simulate topic messages
        tracker = monitor.tracker
        start = time.time()
        msg_count = 0

        while time.time() - start < duration:
            for topic in config.topics:
                tracker.on_message(topic, "std_msgs/String", now_ns=None)
            msg_count += len(config.topics)
            time.sleep(0.01)  # 100Hz simulation

        stats = monitor.get_all_stats()

        rclpy.shutdown()

        return BenchmarkResult(
            "ros_monitoring",
            duration,
            {
                "topics_monitored": len(stats),
                "messages_processed": msg_count,
                "avg_hz_per_topic": {t: s.get("avg_hz", 0) for t, s in stats.items()},
            },
            True,
        )
    except Exception as e:
        return BenchmarkResult("ros_monitoring", duration, {}, False, str(e))


def benchmark_correlation(duration: float = 10.0) -> BenchmarkResult:
    """Benchmark correlation engine."""
    print("Benchmarking correlation engine...")

    try:
        from gpuguard.correlation.correlator import Correlator
        from gpuguard.correlation.time_sync import TimeSynchronizer
        from gpuguard.utils.config import CorrelationConfig
        from gpuguard.utils.time_utils import now_ns

        config = CorrelationConfig(
            sync_tolerance_ms=5,
            min_samples=50,
            rolling_window=200,
        )

        correlator = Correlator(config)
        sync = TimeSynchronizer(tolerance_ms=5)

        # Simulate correlated data
        gpu_metrics = ["utilization_gpu", "memory_used_pct", "temperature_gpu"]
        ros_topics = ["/camera/detection", "/scan", "/cmd_vel"]

        start = time.time()
        samples = 0

        while time.time() - start < duration:
            t = now_ns()
            for gm in gpu_metrics:
                val = 50 + 20 * np.sin(samples * 0.1) + np.random.normal(0, 5)
                correlator.add_gpu_metric(gm, t, val)
                sync.add_gpu_sample(gm, t, val)

            for rt in ros_topics:
                val = 30 + 10 * np.sin(samples * 0.1) + np.random.normal(0, 3)
                correlator.add_ros_metric(rt, t, val)
                sync.add_ros_sample(rt, t, val)

            samples += 1
            time.sleep(0.01)

        # Compute correlations
        results = correlator.compute_correlations()
        granger = correlator.compute_granger_causality()

        return BenchmarkResult(
            "correlation",
            duration,
            {
                "samples_per_stream": samples,
                "correlations_computed": len(results),
                "significant_correlations": len([r for r in results if r.significant]),
                "granger_tests": len(granger),
                "causal_relationships": len([g for g in granger if g.causes_ros]),
            },
            True,
        )
    except Exception as e:
        return BenchmarkResult("correlation", duration, {}, False, str(e))


def benchmark_anomaly_detection(duration: float = 5.0) -> BenchmarkResult:
    """Benchmark anomaly detection."""
    print("Benchmarking anomaly detection...")

    try:
        from gpuguard.anomaly.detector import AnomalyDetector
        from gpuguard.utils.config import AnomalyConfig

        config = AnomalyConfig(
            vram_threshold_pct=85.0,
            temp_threshold_c=80.0,
            latency_spike_threshold=3.0,
        )

        detector = AnomalyDetector(config)

        # Simulate normal then anomalous data
        start = time.time()
        anomalies_found = 0

        while time.time() - start < duration:
            t = time.time_ns()

            # Normal
            detector.check_gpu(0, {
                "memory_used_pct": 60,
                "temperature_gpu": 65,
                "utilization_gpu": 50,
                "power_draw_pct": 50,
                "clock_graphics": 1500,
                "ecc_errors_volatile": 0,
                "is_throttling": False,
            })

            # Anomalous after half duration
            if time.time() - start > duration / 2:
                detector.check_gpu(0, {
                    "memory_used_pct": 95,
                    "temperature_gpu": 88,
                    "utilization_gpu": 95,
                    "power_draw_pct": 95,
                    "clock_graphics": 800,
                    "ecc_errors_volatile": 1,
                    "is_throttling": True,
                })

            anomalies = detector.get_recent_anomalies()
            anomalies_found = len(anomalies)

            time.sleep(0.1)

        return BenchmarkResult(
            "anomaly_detection",
            duration,
            {
                "anomalies_detected": anomalies_found,
                "detection_latency_ms": 100,  # poll interval
            },
            True,
        )
    except Exception as e:
        return BenchmarkResult("anomaly_detection", duration, {}, False, str(e))


def benchmark_end_to_end(duration: float = 30.0) -> BenchmarkResult:
    """Benchmark end-to-end pipeline."""
    print("Benchmarking end-to-end pipeline...")

    try:
        from gpuguard.collector.nvml_collector import MockNVMLCollector
        from gpuguard.collector.sampler import GPUSampler
        from gpuguard.monitor.topic_tracker import TopicTracker
        from gpuguard.correlation.correlator import Correlator
        from gpuguard.correlation.time_sync import TimeSynchronizer
        from gpuguard.utils.config import CollectorConfig, MonitorConfig, CorrelationConfig

        # Setup components
        coll_config = CollectorConfig(poll_interval_ms=100, gpu_indices=[0], buffer_size=5000)
        mon_config = MonitorConfig(topics=["/camera/detection", "/scan"], deadline_ms=33)
        corr_config = CorrelationConfig(sync_tolerance_ms=5, min_samples=30, rolling_window=100)

        collector = MockNVMLCollector(coll_config)
        sampler = GPUSampler(buffer_size=coll_config.buffer_size)
        tracker = TopicTracker(mon_config)
        correlator = Correlator(corr_config)
        sync = TimeSynchronizer(tolerance_ms=5)

        collector.register_callback(lambda s: sampler.add_sample(s))
        tracker.register_callback(lambda t, s: None)

        collector.initialize()
        collector.start()

        start = time.time()
        samples = 0

        while time.time() - start < duration:
            t = time.time_ns()

            # GPU data
            gpu_state = collector.sample_now().get(0)
            if gpu_state:
                sampler.add_sample(gpu_state)

                # Feed correlator
                correlator.add_gpu_metric("utilization_gpu", t, gpu_state.utilization_gpu)
                correlator.add_gpu_metric("memory_used_pct", t, gpu_state.memory_used_pct)
                correlator.add_gpu_metric("temperature_gpu", t, gpu_state.temperature_gpu)

                sync.add_gpu_sample("utilization_gpu", t, gpu_state.utilization_gpu)
                sync.add_gpu_sample("memory_used_pct", t, gpu_state.memory_used_pct)

            # ROS data
            for topic in mon_config.topics:
                tracker.on_message(topic, "std_msgs/String", t)
                hz = 30 + np.random.normal(0, 2)
                latency = 10 + np.random.exponential(5)
                correlator.add_ros_metric(topic, t, hz)
                correlator.add_ros_metric(f"{topic}_latency", t, latency)
                sync.add_ros_sample(topic, t, hz)

            samples += 1
            time.sleep(0.01)

        # Compute final correlations
        correlations = correlator.compute_correlations()

        collector.stop()

        return BenchmarkResult(
            "end_to_end",
            duration,
            {
                "total_samples": samples,
                "gpu_samples": sampler.get_stats().total_samples,
                "correlations_computed": len(correlations),
                "sync_pairs": len(sync.get_sync_pairs()),
            },
            True,
        )
    except Exception as e:
        return BenchmarkResult("end_to_end", duration, {}, False, str(e))


def now_ns():
    return time.time_ns()


def run_benchmarks(selected: List[str], duration: float, output: Path) -> List[BenchmarkResult]:
    """Run selected benchmarks."""
    benchmarks = {
        "gpu_collection": benchmark_gpu_collection,
        "ros_monitoring": benchmark_ros_monitoring,
        "correlation": benchmark_correlation,
        "anomaly_detection": benchmark_anomaly_detection,
        "end_to_end": benchmark_end_to_end,
    }

    results = []

    for name in selected:
        if name not in benchmarks:
            print(f"Unknown benchmark: {name}")
            continue

        print(f"\n{'='*50}")
        print(f"Running: {name}")
        print(f"{'='*50}")

        result = benchmarks[name](duration)
        results.append(result)

        if result.success:
            print(f"✓ {name} passed")
            for k, v in result.metrics.items():
                print(f"  {k}: {v}")
        else:
            print(f"✗ {name} failed: {result.error}")

    # Save results
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w') as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"\nResults saved to {output}")

    return results


def main():
    parser = argparse.ArgumentParser(description="GPUGuard Benchmark Suite")
    parser.add_argument(
        "--benchmarks", "-b",
        nargs="+",
        default=["gpu_collection", "ros_monitoring", "correlation", "anomaly_detection", "end_to_end"],
        help="Benchmarks to run"
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=10.0,
        help="Duration per benchmark in seconds"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("artifacts/benchmark_results.json"),
        help="Output file for results"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available benchmarks"
    )

    args = parser.parse_args()

    if args.list:
        print("Available benchmarks:")
        print("  gpu_collection    - GPU telemetry collection rate")
        print("  ros_monitoring    - ROS 2 topic monitoring")
        print("  correlation       - GPU-ROS correlation engine")
        print("  anomaly_detection - Anomaly detection")
        print("  end_to_end        - Full pipeline integration")
        return 0

    print(f"GPUGuard Benchmark Suite")
    print(f"Duration per benchmark: {duration}s")
    print(f"Output: {output}")

    results = run_benchmarks(args.benchmarks, args.duration, args.output)

    # Summary
    passed = sum(1 for r in results if r.success)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Summary: {passed}/{total} passed")
    print(f"{'='*50}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())