"""GPUGuard Dashboard - Plotly Dash application."""
import os
from pathlib import Path
import dash
from dash import Dash
import dash_bootstrap_components as dbc

from gpuguard.dashboard.layouts import create_main_layout
from gpuguard.dashboard.callbacks import register_callbacks
from gpuguard.utils.config import get_config, DashboardConfig
from gpuguard.utils.logging import get_logger, init_logging

logger = get_logger("dashboard.app")


def create_dash_app(config: DashboardConfig = None) -> Dash:
    """Create the Dash application."""
    if config is None:
        config = get_config().dashboard

    # Initialize logging
    init_logging()

    # Create assets directory
    assets_path = Path(__file__).parent / "assets"
    assets_path.mkdir(exist_ok=True)

    # Create GPU icon SVG
    icon_path = assets_path / "gpu_icon.svg"
    if not icon_path.exists():
        icon_path.write_text("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <rect x="2" y="3" width="20" height="18" rx="2"/>
  <line x1="2" y1="9" x2="22" y2="9"/>
  <line x1="2" y1="15" x2="22" y2="15"/>
  <line x1="9" y1="3" x2="9" y2="21"/>
  <line x1="15" y1="3" x2="15" y2="21"/>
</svg>""")

    # Create Dash app
    app = Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.CYBORG,  # Dark theme
            dbc.icons.FONT_AWESOME,
        ],
        assets_folder=str(assets_path),
        title="GPUGuard - GPU Observability for ROS 2",
        update_title=None,
        suppress_callback_exceptions=True,
    )

    # Set layout
    app.layout = create_main_layout()

    # Register callbacks
    register_callbacks(app)

    return app


def run_dashboard(
    host: str = "0.0.0.0",
    port: int = 8050,
    debug: bool = False,
):
    """Run the dashboard server."""
    config = get_config()
    dash_config = config.dashboard

    host = host or dash_config.host
    port = port or dash_config.port

    app = create_dash_app(dash_config)

    logger.info(f"Starting GPUGuard Dashboard on http://{host}:{port}")

    app.run(
        host=host,
        port=port,
        debug=debug,
        dev_tools_ui=debug,
        dev_tools_props_check=debug,
    )


# For direct module execution
if __name__ == "__main__":
    run_dashboard()