"""GPU Collector CLI entry point."""
import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from gpuguard.collector.nvml_collector import NVMLCollector, MockNVMLCollector
from gpuguard.collector.sampler import GPUSampler
from gpuguard.utils.config import load_config, CollectorConfig
from gpuguard.utils.logging import init_logging, get_logger
from gpuguard.utils.time_utils import now_ns

logger = get_logger("collector.cli")


class CollectorApp:
    """GPU Collector application."""

    def __init__(self, config_path: Optional[Path] = None, mock: bool = False):
        self.config_path = config_path
        self.mock = mock
        self.collector = None
        self.sampler = None
        self.running = False

    def setup(self) -> bool:
        """Initialize components."""
        # Load config
        config = load_config(self.config_path)
        collector_config = config.collector

        # Initialize logging
        init_logging(self.config_path)

        # Create collector
        if self.mock:
            logger.info("Using mock NVML collector")
            self.collector = MockNVMLCollector(collector_config)
        else:
            self.collector = NVMLCollector(collector_config)

        # Create sampler
        self.sampler = GPUSampler(buffer_size=collector_config.buffer_size)

        # Register sampler as callback
        self.collector.register_callback(self._on_gpu_state)

        # Initialize collector
        if not self.collector.initialize():
            logger.error("Failed to initialize collector")
            return False

        # Cache GPU infos in sampler
        for gpu_id, info in self.collector.get_all_gpu_infos().items():
            self.sampler.set_gpu_info(gpu_id, info)

        return True

    def _on_gpu_state(self, state) -> None:
        """Handle new GPU state from collector."""
        self.sampler.add_sample(state)

    def run(self) -> int:
        """Run the collector."""
        if not self.setup():
            return 1

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start collector
        if not self.collector.start():
            logger.error("Failed to start collector")
            return 1

        self.running = True
        logger.info("GPU Collector running. Press Ctrl+C to stop.")

        try:
            # Print periodic stats
            while self.running:
                time.sleep(10.0)
                self._print_stats()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

        return 0

    def _print_stats(self) -> None:
        """Print collector and sampler stats."""
        coll_stats = self.collector.get_stats()
        samp_stats = self.sampler.get_stats()

        logger.info(
            f"Collector: samples={coll_stats.samples_collected}, "
            f"failed={coll_stats.samples_failed}, gpus={coll_stats.gpu_count}"
        )
        logger.info(
            f"Sampler: total={samp_stats.total_samples}, "
            f"overflows={samp_stats.buffer_overflows}"
        )

        # Print latest GPU states
        for gpu_id in self.sampler.get_all_gpu_ids():
            latest = self.sampler.get_latest(gpu_id)
            if latest:
                logger.info(
                    f"GPU {gpu_id}: VRAM={latest.memory_used_pct:.1f}%, "
                    f"GPU={latest.utilization_gpu:.1f}%, "
                    f"Temp={latest.temperature_gpu:.1f}°C, "
                    f"Power={latest.power_draw:.1f}W, "
                    f"Clocks={latest.clock_graphics}/{latest.clock_sm}MHz"
                )

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def shutdown(self) -> None:
        """Clean shutdown."""
        self.running = False
        if self.collector:
            self.collector.shutdown()
        logger.info("Collector shutdown complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GPUGuard GPU Telemetry Collector")
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to configuration YAML file"
    )
    parser.add_argument(
        "--mock", "-m",
        action="store_true",
        help="Use mock collector (no GPU required)"
    )
    parser.add_argument(
        "--poll-interval", "-p",
        type=int,
        default=100,
        help="Poll interval in milliseconds"
    )
    parser.add_argument(
        "--gpu-indices", "-g",
        type=str,
        default="0",
        help="Comma-separated GPU indices to monitor"
    )
    parser.add_argument(
        "--log-level", "-l",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level"
    )

    args = parser.parse_args()

    # Override config with CLI args
    import os
    if args.poll_interval:
        os.environ["GPUGUARD_COLLECTOR__POLL_INTERVAL_MS"] = str(args.poll_interval)
    if args.gpu_indices:
        os.environ["GPUGUARD_COLLECTOR__GPU_INDICES"] = args.gpu_indices
    if args.log_level:
        os.environ["GPUGUARD_LOGGING__LEVEL"] = args.log_level

    app = CollectorApp(config_path=args.config, mock=args.mock)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())