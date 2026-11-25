"""Dashboard layout definitions."""
import dash_bootstrap_components as dbc
from dash import html, dcc


def create_header() -> dbc.Navbar:
    """Create the dashboard header/navbar."""
    return dbc.Navbar(
        dbc.Container([
            html.A(
                dbc.Row([
                    dbc.Col(html.Img(src="/assets/gpu_icon.svg", height="32px"), width="auto"),
                    dbc.Col(dbc.NavbarBrand("GPUGuard", className="ms-2 fw-bold fs-4", style={"color": "#1e293b"})),
                ], align="center", className="g-0"),
                href="/",
                style={"textDecoration": "none"},
            ),
            dbc.NavbarToggler(id="navbar-toggler"),
            dbc.Collapse([
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("Overview", href="#overview", external_link=True, className="text-muted fw-medium px-3")),
                    dbc.NavItem(dbc.NavLink("GPU Metrics", href="#gpu", external_link=True, className="text-muted fw-medium px-3")),
                    dbc.NavItem(dbc.NavLink("ROS 2 Topics", href="#ros", external_link=True, className="text-muted fw-medium px-3")),
                    dbc.NavItem(dbc.NavLink("Correlations", href="#corr", external_link=True, className="text-muted fw-medium px-3")),
                    dbc.NavItem(dbc.NavLink("Anomalies", href="#anomalies", external_link=True, className="text-muted fw-medium px-3")),
                ], className="ms-auto", navbar=True),
                dbc.NavItem([
                    dbc.Button("⚙️ Settings", id="settings-btn", color="outline-primary", size="sm", className="fw-medium"),
                ], className="ms-3"),
            ], id="navbar-collapse", navbar=True),
        ], fluid=True),
        color="white",
        dark=False,
        className="mb-4 shadow-sm border-bottom",
        style={"borderColor": "#e2e8f0"},
    )


def create_gpu_overview_row() -> dbc.Row:
    """Create GPU overview metric cards row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Span("⚡", className="me-2 fs-3"),
                        html.H6("GPU Utilization", className="text-muted mb-1"),
                    ], className="d-flex align-items-center"),
                    html.H2(id="gpu-util-value", className="fw-bold mb-1", style={"color": "#2563eb"}),
                    html.Small("Target: < 80%", className="text-muted"),
                    html.Div(id="gpu-util-trend", className="mt-2 small"),
                ])
            ], className="h-100 metric-card", style={"borderLeft": "4px solid #2563eb"}),
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Span("💾", className="me-2 fs-3"),
                        html.H6("VRAM Usage", className="text-muted mb-1"),
                    ], className="d-flex align-items-center"),
                    html.H2(id="vram-value", className="fw-bold mb-1", style={"color": "#f59e0b"}),
                    html.Small(id="vram-detail", className="text-muted"),
                    html.Div(id="vram-trend", className="mt-2 small"),
                ])
            ], className="h-100 metric-card", style={"borderLeft": "4px solid #f59e0b"}),
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Span("🌡️", className="me-2 fs-3"),
                        html.H6("Temperature", className="text-muted mb-1"),
                    ], className="d-flex align-items-center"),
                    html.H2(id="temp-value", className="fw-bold mb-1", style={"color": "#ef4444"}),
                    html.Small(id="temp-detail", className="text-muted"),
                    html.Div(id="temp-trend", className="mt-2 small"),
                ])
            ], className="h-100 metric-card", style={"borderLeft": "4px solid #ef4444"}),
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Span("⚡", className="me-2 fs-3"),
                        html.H6("Power Draw", className="text-muted mb-1"),
                    ], className="d-flex align-items-center"),
                    html.H2(id="power-value", className="fw-bold mb-1", style={"color": "#06b6d4"}),
                    html.Small(id="power-detail", className="text-muted"),
                    html.Div(id="power-trend", className="mt-2 small"),
                ])
            ], className="h-100 metric-card", style={"borderLeft": "4px solid #06b6d4"}),
        ], md=3),
    ], className="mb-4 g-3")


def create_gpu_charts_row() -> dbc.Row:
    """Create GPU time series charts row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("GPU Utilization & Memory", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    dcc.Graph(id="gpu-util-chart", config={"displayModeBar": False}),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Temperature & Power", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    dcc.Graph(id="gpu-temp-power-chart", config={"displayModeBar": False}),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=6),
    ], className="mb-4 g-3")


def create_gpu_clocks_row() -> dbc.Row:
    """Create GPU clocks row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("GPU Clock Frequencies", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    dcc.Graph(id="gpu-clocks-chart", config={"displayModeBar": False}),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=12),
    ], className="mb-4 g-3")


def create_ros_overview_row() -> dbc.Row:
    """Create ROS 2 topics overview row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("ROS 2 Topic Rates", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    dcc.Graph(id="ros-hz-chart", config={"displayModeBar": False}),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Topic Latencies", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    dcc.Graph(id="ros-latency-chart", config={"displayModeBar": False}),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=6),
    ], className="mb-4 g-3")


def create_ros_details_row() -> dbc.Row:
    """Create ROS 2 topics detail table."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Topic Details", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    html.Div(id="ros-topic-table"),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=12),
    ], className="mb-4 g-3")


def create_correlation_row() -> dbc.Row:
    """Create correlation analysis row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("GPU ↔ ROS 2 Correlation Matrix", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    dcc.Graph(id="correlation-heatmap", config={"displayModeBar": False}),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Significant Correlations", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    html.Div(id="significant-correlations"),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=4),
    ], className="mb-4 g-3")


def create_granger_row() -> dbc.Row:
    """Create Granger causality row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Granger Causality (GPU → ROS)", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    html.Div(id="granger-results"),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=12),
    ], className="mb-4 g-3")


def create_anomaly_row() -> dbc.Row:
    """Create anomaly detection row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Anomaly Timeline", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    dcc.Graph(id="anomaly-timeline", config={"displayModeBar": False}),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Active Alerts", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    html.Div(id="active-alerts"),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=4),
    ], className="mb-4 g-3")


def create_chain_latency_row() -> dbc.Row:
    """Create latency chain analysis row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Latency Chains", className="mb-0 fw-medium"),
                ], className="bg-transparent border-0 pb-0"),
                dbc.CardBody([
                    html.Div(id="chain-latency"),
                ], className="pt-0"),
            ], className="h-100 chart-card"),
        ], md=12),
    ], className="mb-4 g-3")


def create_footer() -> html.Footer:
    """Create dashboard footer."""
    return html.Footer(
        dbc.Container([
            html.Hr(className="my-4", style={"borderColor": "#e2e8f0"}),
            html.Div([
                html.P([
                    "GPUGuard v0.1.0",
                    html.Span(" • ", className="mx-2"),
                    html.A("GitHub", href="https://github.com/darshan-stack/GPUGuard", target="_blank", className="text-decoration-none fw-medium"),
                    html.Span(" • ", className="mx-2"),
                    html.A("Documentation", href="/docs", className="text-decoration-none fw-medium"),
                ], className="text-center text-muted small mb-2"),
                html.P("AI-powered GPU observability for ROS 2 robotics", className="text-center text-muted small"),
            ]),
        ], fluid=True),
        className="mt-5 py-4",
        style={"backgroundColor": "#f8fafc", "borderTop": "1px solid #e2e8f0"},
    )


def create_main_layout() -> html.Div:
    """Create the complete dashboard layout."""
    return html.Div([
        # Stores for data
        dcc.Store(id="gpu-data-store"),
        dcc.Store(id="ros-data-store"),
        dcc.Store(id="correlation-data-store"),
        dcc.Store(id="anomaly-data-store"),
        dcc.Store(id="settings-store"),

        # WebSocket connection
        html.Div(id="ws-connection"),

        # Header
        create_header(),

        # Main content
        dbc.Container([
            # GPU Section
            html.Div([
                html.H2("GPU Metrics", id="gpu", className="section-title fw-bold"),
                html.P("Real-time GPU telemetry from NVML", className="section-subtitle text-muted"),
            ], className="section-header"),
            create_gpu_overview_row(),
            create_gpu_charts_row(),
            create_gpu_clocks_row(),

            # ROS 2 Section
            html.Div([
                html.H2("ROS 2 Topics", id="ros", className="section-title fw-bold"),
                html.P("Topic rates, latencies, and deadline monitoring", className="section-subtitle text-muted"),
            ], className="section-header"),
            create_ros_overview_row(),
            create_ros_details_row(),

            # Correlation Section
            html.Div([
                html.H2("Correlation Analysis", id="corr", className="section-title fw-bold"),
                html.P("GPU-ROS cross-correlation with lag detection & Granger causality", className="section-subtitle text-muted"),
            ], className="section-header"),
            create_correlation_row(),
            create_granger_row(),

            # Anomaly Section
            html.Div([
                html.H2("Anomaly Detection", id="anomalies", className="section-title fw-bold"),
                html.P("Statistical thresholds + Isolation Forest anomaly detection", className="section-subtitle text-muted"),
            ], className="section-header"),
            create_anomaly_row(),

            # Chain Latency
            html.Div([
                html.H2("Latency Chains", id="chains", className="section-title fw-bold"),
                html.P("End-to-end pipeline latency analysis", className="section-subtitle text-muted"),
            ], className="section-header"),
            create_chain_latency_row(),

            # Footer
            create_footer(),
        ], fluid=True, className="px-4 py-3"),

        # Interval for periodic updates (fallback)
        dcc.Interval(id="update-interval", interval=500, n_intervals=0),

        # Settings modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Settings", className="fw-medium")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Row([
                        dbc.Label("Update Interval (ms)", width=4, className="fw-medium"),
                        dbc.Col([
                            dbc.Input(id="setting-update-interval", type="number", value=500, min=100, max=5000, className="form-control-sm"),
                        ], width=8),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Max Data Points", width=4, className="fw-medium"),
                        dbc.Col([
                            dbc.Input(id="setting-max-points", type="number", value=500, min=100, max=5000, className="form-control-sm"),
                        ], width=8),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Theme", width=4, className="fw-medium"),
                        dbc.Col([
                            dbc.Select(
                                id="setting-theme",
                                options=[
                                    {"label": "Light (Default)", "value": "light"},
                                    {"label": "Dark", "value": "dark"},
                                ],
                                value="light",
                                className="form-control-sm",
                            ),
                        ], width=8),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Correlation Threshold", width=4, className="fw-medium"),
                        dbc.Col([
                            dbc.Input(id="setting-corr-threshold", type="number", value=0.5, min=0, max=1, step=0.1, className="form-control-sm"),
                        ], width=8),
                    ], className="mb-3"),
                ]),
            ]),
            dbc.ModalFooter([
                dbc.Button("Save", id="settings-save", color="primary", size="sm"),
                dbc.Button("Cancel", id="settings-cancel", color="outline-secondary", size="sm"),
            ]),
        ], id="settings-modal", is_open=False, size="lg"),
    ], className="dashboard-container")