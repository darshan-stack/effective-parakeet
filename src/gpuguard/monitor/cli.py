"""ROS 2 Monitor CLI entry point."""
import argparse
import signal
import sys
import time
from pathlib import Path

import rclpy

from gpuguard.monitor.ros_monitor import create_ros_monitor, spin_ros_monitor
from gpuguard.utils.config import load_config
from gpuguard.utils.logging import init_logging, get_logger

logger = get_logger("monitor.cli")


class ROSMonitorApp:
    """ROS 2 Monitor application."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self.node = None
        self.spin_thread = None
        self.running = False

    def setup(self) -> bool:
        """Initialize ROS 2 and node."""
        try:
            # Load config
            load_config(self.config_path)

            # Initialize logging
            init_logging(self.config_path)

            # Initialize ROS 2
            rclpy.init()

            # Create monitor node
            self.node = create_ros_monitor()

            # Start monitoring
            self.node.start_monitoring()

            # Start spinner thread
            self.spin_thread = spin_ros_monitor(self.node)

            return True

        except Exception as e:
            logger.error(f"Failed to setup ROS monitor: {e}")
            return False

    def run(self) -> int:
        """Run the monitor."""
        if not self.setup():
            return 1

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.running = True
        logger.info("ROS 2 Monitor running. Press Ctrl+C to stop.")

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
        """Print topic statistics."""
        stats = self.node.get_all_stats()
        deadline_status = self.node.get_deadline_status()

        logger.info(f"Monitoring {len(stats)} topics:")

        for topic, data in stats.items():
            dl = deadline_status.get(topic, {})
            logger.info(
                f"  {topic}: {data['current_hz']:.1f}Hz "
                f"(avg: {data['avg_hz']:.1f}Hz), "
                f"latency: {data['avg_latency_ms']:.2f}ms, "
                f"misses: {dl.get('consecutive_misses', 0)}"
            )

        # Print chain latencies
        for chain in ["perception", "navigation", "localization"]:
            chain_data = self.node.get_chain_latency(chain)
            if chain_data and chain_data["topics"]:
                logger.info(f"Chain '{chain}':")
                for t, lat in chain_data["topics"].items():
                    logger.info(f"  {t}: avg={lat['avg_ms']:.2f}ms, max={lat['max_ms']:.2f}ms")

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def shutdown(self) -> None:
        """Clean shutdown."""
        self.running = False
        if self.node:
            self.node.shutdown()
        rclpy.shutdown()
        logger.info("ROS Monitor shutdown complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GPUGuard ROS 2 Topic Monitor")
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to configuration YAML file"
    )
    parser.add_argument(
        "--domain", "-d",
        type=int,
        default=0,
        help="ROS_DOMAIN_ID"
    )
    parser.add_argument(
        "--node-name", "-n",
        type=str,
        default="gpuguard_monitor",
        help="ROS 2 node name"
    )
    parser.add_argument(
        "--topics", "-t",
        type=str,
        help="Comma-separated topics to monitor"
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
    if args.domain is not None:
        os.environ["GPUGUARD_ROS2__DOMAIN_ID"] = str(args.domain)
    if args.node_name:
        os.environ["GPUGUARD_ROS2__NODE_NAME"] = args.node_name
    if args.topics:
        os.environ["GPUGUARD_MONITOR__TOPICS"] = args.topics
    if args.log_level:
        os.environ["GPUGUARD_LOGGING__LEVEL"] = args.log_level

    app = ROSMonitorApp(config_path=args.config)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())