"""GPUGuard Dashboard package."""
from gpuguard.dashboard.app import create_dash_app, run_dashboard
from gpuguard.dashboard.layouts import create_main_layout
from gpuguard.dashboard.callbacks import register_callbacks
from gpuguard.dashboard.components import (
    create_metric_card,
    create_gauge_chart,
    create_time_series_chart,
    create_correlation_heatmap,
    create_anomaly_timeline,
    create_topic_hz_chart,
)
from gpuguard.dashboard.cli import main as dashboard_cli_main

__all__ = [
    "create_dash_app",
    "run_dashboard",
    "create_main_layout",
    "register_callbacks",
    "create_metric_card",
    "create_gauge_chart",
    "create_time_series_chart",
    "create_correlation_heatmap",
    "create_anomaly_timeline",
    "create_topic_hz_chart",
    "dashboard_cli_main",
]