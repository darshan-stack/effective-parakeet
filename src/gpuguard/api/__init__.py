"""GPUGuard API package."""
from gpuguard.api.main import create_app, run_api
from gpuguard.api.routes import router, set_data_stores, broadcast_gpu_state, broadcast_topic_stats, broadcast_correlation, broadcast_anomaly
from gpuguard.api.websocket_manager import WebSocketManager, get_websocket_manager
from gpuguard.api.cli import main as api_cli_main

__all__ = [
    "create_app",
    "run_api",
    "router",
    "set_data_stores",
    "broadcast_gpu_state",
    "broadcast_topic_stats",
    "broadcast_correlation",
    "broadcast_anomaly",
    "WebSocketManager",
    "get_websocket_manager",
    "api_cli_main",
]