#!/usr/bin/env python3
"""GPUGuard System Launcher - Starts all components."""
import argparse
import subprocess
import sys
import time
import signal
import os
from pathlib import Path
from typing import List, Optional


class ProcessManager:
    """Manages subprocesses for GPUGuard components."""

    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.running = False

    def start(self, cmd: List[str], name: str, env: Optional[dict] = None) -> subprocess.Popen:
        """Start a subprocess."""
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        print(f"[GPUGuard] Starting {name}: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self.processes.append(proc)
        return proc

    def stop_all(self):
        """Stop all processes."""
        self.running = False
        print("\n[GPUGuard] Shutting down all components...")
        for proc in self.processes:
            if proc.poll() is None:
                proc.terminate()
        # Wait for graceful shutdown
        for proc in self.processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        print("[GPUGuard] All components stopped.")


def run_mock_demo(manager: ProcessManager, args):
    """Run full demo with mock collector."""
    venv_python = sys.executable

    # Start collector (mock)
    manager.start([
        venv_python, "-m", "gpuguard.collector.cli",
        "--mock",
        "--poll-interval", str(args.poll_interval),
        "--log-level", args.log_level
    ], "GPU Collector (Mock)")

    time.sleep(2)

    # Start ROS monitor
    manager.start([
        venv_python, "-m", "gpuguard.monitor.cli",
        "--log-level", args.log_level
    ], "ROS 2 Monitor")

    time.sleep(1)

    # Start API
    manager.start([
        venv_python, "-m", "gpuguard.api.cli",
        "--host", args.api_host,
        "--port", str(args.api_port),
        "--log-level", args.log_level
    ], "API Server")

    time.sleep(1)

    # Start Dashboard
    manager.start([
        venv_python, "-m", "gpuguard.dashboard.cli",
        "--host", args.dashboard_host,
        "--port", str(args.dashboard_port),
        "--log-level", args.log_level
    ], "Dashboard")

    print(f"\n[GPUGuard] Demo running!")
    print(f"  Dashboard: http://{args.dashboard_host}:{args.dashboard_port}")
    print(f"  API:       http://{args.api_host}:{args.api_port}")
    print(f"  Press Ctrl+C to stop\n")


def run_production(manager: ProcessManager, args):
    """Run production mode with real GPU."""
    venv_python = sys.executable

    # Start collector
    manager.start([
        venv_python, "-m", "gpuguard.collector.cli",
        "--poll-interval", str(args.poll_interval),
        "--gpu-indices", args.gpu_indices,
        "--log-level", args.log_level
    ], "GPU Collector")

    time.sleep(2)

    # Start ROS monitor
    manager.start([
        venv_python, "-m", "gpuguard.monitor.cli",
        "--domain", str(args.ros_domain),
        "--log-level", args.log_level
    ], "ROS 2 Monitor")

    time.sleep(1)

    # Start API
    manager.start([
        venv_python, "-m", "gpuguard.api.cli",
        "--host", args.api_host,
        "--port", str(args.api_port),
        "--log-level", args.log_level
    ], "API Server")

    time.sleep(1)

    # Start Dashboard
    manager.start([
        venv_python, "-m", "gpuguard.dashboard.cli",
        "--host", args.dashboard_host,
        "--port", str(args.dashboard_port),
        "--log-level", args.log_level
    ], "Dashboard")

    print(f"\n[GPUGuard] Production running!")
    print(f"  Dashboard: http://{args.dashboard_host}:{args.dashboard_port}")
    print(f"  API:       http://{args.api_host}:{args.api_port}")
    print(f"  Press Ctrl+C to stop\n")


def run_ros2_native(args):
    """Run via ROS 2 launch."""
    env = os.environ.copy()
    env["ROS_DOMAIN_ID"] = str(args.ros_domain)

    cmd = [
        "ros2", "launch", "gpuguard_ros2", "gpuguard.launch.py",
        f"use_mock:={'true' if args.mock else 'false'}",
        f"gpu_indices:={args.gpu_indices}",
        f"poll_interval:={args.poll_interval}",
        f"log_level:={args.log_level}",
    ]

    print(f"[GPUGuard] Running ROS 2 native: {' '.join(cmd)}")
    subprocess.run(cmd, env=env)


def main():
    parser = argparse.ArgumentParser(description="GPUGuard System Launcher")
    parser.add_argument(
        "mode",
        choices=["mock", "prod", "ros2", "collector", "monitor", "api", "dashboard"],
        help="Run mode"
    )
    parser.add_argument("--mock", action="store_true", help="Use mock collector (for ros2 mode)")
    parser.add_argument("--poll-interval", type=int, default=100, help="Poll interval ms")
    parser.add_argument("--gpu-indices", default="0", help="GPU indices")
    parser.add_argument("--ros-domain", type=int, default=0, help="ROS_DOMAIN_ID")
    parser.add_argument("--api-host", default="0.0.0.0", help="API host")
    parser.add_argument("--api-port", type=int, default=8080, help="API port")
    parser.add_argument("--dashboard-host", default="0.0.0.0", help="Dashboard host")
    parser.add_argument("--dashboard-port", type=int, default=8050, help="Dashboard port")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    # Set environment variables for config
    os.environ["GPUGUARD_COLLECTOR__POLL_INTERVAL_MS"] = str(args.poll_interval)
    os.environ["GPUGUARD_COLLECTOR__GPU_INDICES"] = args.gpu_indices
    os.environ["GPUGUARD_ROS2__DOMAIN_ID"] = str(args.ros_domain)
    os.environ["GPUGUARD_API__HOST"] = args.api_host
    os.environ["GPUGUARD_API__PORT"] = str(args.api_port)
    os.environ["GPUGUARD_DASHBOARD__HOST"] = args.dashboard_host
    os.environ["GPUGUARD_DASHBOARD__PORT"] = str(args.dashboard_port)
    os.environ["GPUGUARD_LOGGING__LEVEL"] = args.log_level

    manager = ProcessManager()

    def signal_handler(signum, frame):
        manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.mode == "mock":
            manager.running = True
            run_mock_demo(manager, args)
            # Keep running
            while manager.running:
                time.sleep(1)

        elif args.mode == "prod":
            manager.running = True
            run_production(manager, args)
            while manager.running:
                time.sleep(1)

        elif args.mode == "ros2":
            run_ros2_native(args)

        elif args.mode == "collector":
            subprocess.run([
                sys.executable, "-m", "gpuguard.collector.cli",
                "--mock" if args.mock else "",
                "--poll-interval", str(args.poll_interval),
                "--gpu-indices", args.gpu_indices,
                "--log-level", args.log_level
            ])

        elif args.mode == "monitor":
            subprocess.run([
                sys.executable, "-m", "gpuguard.monitor.cli",
                "--domain", str(args.ros_domain),
                "--log-level", args.log_level
            ])

        elif args.mode == "api":
            subprocess.run([
                sys.executable, "-m", "gpuguard.api.cli",
                "--host", args.api_host,
                "--port", str(args.api_port),
                "--log-level", args.log_level
            ])

        elif args.mode == "dashboard":
            subprocess.run([
                sys.executable, "-m", "gpuguard.dashboard.cli",
                "--host", args.dashboard_host,
                "--port", str(args.dashboard_port),
                "--log-level", args.log_level
            ])

    except KeyboardInterrupt:
        pass
    finally:
        manager.stop_all()


if __name__ == "__main__":
    main()