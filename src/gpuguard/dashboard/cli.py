"""Dashboard CLI entry point."""
import argparse
import sys
from pathlib import Path

from gpuguard.dashboard.app import run_dashboard
from gpuguard.utils.config import load_config
from gpuguard.utils.logging import init_logging, get_logger

logger = get_logger("dashboard.cli")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GPUGuard Dashboard")
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to configuration YAML file"
    )
    parser.add_argument(
        "--host", "-H",
        type=str,
        default="0.0.0.0",
        help="Host to bind to"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8050,
        help="Port to bind to"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode"
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
    if args.config:
        os.environ["GPUGUARD_CONFIG_FILE"] = str(args.config)
    if args.host:
        os.environ["GPUGUARD_DASHBOARD__HOST"] = args.host
    if args.port:
        os.environ["GPUGUARD_DASHBOARD__PORT"] = str(args.port)
    if args.log_level:
        os.environ["GPUGUARD_LOGGING__LEVEL"] = args.log_level

    # Load config and init logging
    load_config(args.config)
    init_logging(args.config)

    logger.info(f"Starting GPUGuard Dashboard on {args.host}:{args.port}")

    run_dashboard(host=args.host, port=args.port, debug=args.debug)

    return 0


if __name__ == "__main__":
    sys.exit(main())