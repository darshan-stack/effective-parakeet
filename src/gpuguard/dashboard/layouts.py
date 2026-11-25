"""Dashboard layout definitions."""
import dash_bootstrap_components as dbc
from dash import html, dcc


def create_header() -> dbc.Navbar:
    """Create the dashboard header/navbar."""
    return dbc.Navbar(
        dbc.Container([
            html.A(
                dbc.Row([
                    dbc.Col(html.Img(src="/assets/gpu_icon.svg", height="30px"), width="auto"),
                    dbc.Col(dbc.NavbarBrand("GPUGuard", className="ms-2 fw-bold")),
                ], align="center", className="g-0"),
                href="/",
                style={"textDecoration": "none"},
            ),
            dbc.NavbarToggler(id="navbar-toggler"),
            dbc.Collapse([
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("Overview", href="#overview", external_link=True)),
                    dbc.NavItem(dbc.NavLink("GPU Metrics", href="#gpu", external_link=True)),
                    dbc.NavItem(dbc.NavLink("ROS 2 Topics", href="#ros", external_link=True)),
                    dbc.NavItem(dbc.NavLink("Correlations", href="#corr", external_link=True)),
                    dbc.NavItem(dbc.NavLink("Anomalies", href="#anomalies", external_link=True)),
                ], className="ms-auto", navbar=True),
                dbc.NavItem([
                    dbc.Button("⚙️ Settings", id="settings-btn", color="outline-light", size="sm"),
                ]),
            ], id="navbar-collapse", navbar=True),
        ], fluid=True),
        color="dark",
        dark=True,
        className="mb-4",
    )


def create_gpu_overview_row() -> dbc.Row:
    """Create GPU overview metric cards row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("GPU Utilization", className="text-muted mb-1"),
                    html.H2(id="gpu-util-value", className="text-primary mb-0"),
                    html.Small("Target: < 80%", className="text-muted"),
                ])
            ], className="h-100"),
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("VRAM Usage", className="text-muted mb-1"),
                    html.H2(id="vram-value", className="text-warning mb-0"),
                    html.Small(id="vram-detail", className="text-muted"),
                ])
            ], className="h-100"),
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Temperature", className="text-muted mb-1"),
                    html.H2(id="temp-value", className="text-danger mb-0"),
                    html.Small(id="temp-detail", className="text-muted"),
                ])
            ], className="h-100"),
        ], md=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Power Draw", className="text-muted mb-1"),
                    html.H2(id="power-value", className="text-info mb-0"),
                    html.Small(id="power-detail", className="text-muted"),
                ])
            ], className="h-100"),
        ], md=3),
    ], className="mb-4")


def create_gpu_charts_row() -> dbc.Row:
    """Create GPU time series charts row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("GPU Utilization & Memory"),
                dbc.CardBody([
                    dcc.Graph(id="gpu-util-chart", config={"displayModeBar": False}),
                ]),
            ]),
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Temperature & Power"),
                dbc.CardBody([
                    dcc.Graph(id="gpu-temp-power-chart", config={"displayModeBar": False}),
                ]),
            ]),
        ], md=6),
    ], className="mb-4")


def create_gpu_clocks_row() -> dbc.Row:
    """Create GPU clocks row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("GPU Clock Frequencies"),
                dbc.CardBody([
                    dcc.Graph(id="gpu-clocks-chart", config={"displayModeBar": False}),
                ]),
            ]),
        ], md=12),
    ], className="mb-4")


def create_ros_overview_row() -> dbc.Row:
    """Create ROS 2 topics overview row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("ROS 2 Topic Rates"),
                dbc.CardBody([
                    dcc.Graph(id="ros-hz-chart", config={"displayModeBar": False}),
                ]),
            ]),
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Topic Latencies"),
                dbc.CardBody([
                    dcc.Graph(id="ros-latency-chart", config={"displayModeBar": False}),
                ]),
            ]),
        ], md=6),
    ], className="mb-4")


def create_ros_details_row() -> dbc.Row:
    """Create ROS 2 topics detail table."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Topic Details"),
                dbc.CardBody([
                    html.Div(id="ros-topic-table"),
                ]),
            ]),
        ], md=12),
    ], className="mb-4")


def create_correlation_row() -> dbc.Row:
    """Create correlation analysis row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("GPU ↔ ROS 2 Correlation Matrix"),
                dbc.CardBody([
                    dcc.Graph(id="correlation-heatmap", config={"displayModeBar": False}),
                ]),
            ]),
        ], md=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Significant Correlations"),
                dbc.CardBody([
                    html.Div(id="significant-correlations"),
                ]),
            ]),
        ], md=4),
    ], className="mb-4")


def create_granger_row() -> dbc.Row:
    """Create Granger causality row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Granger Causality (GPU → ROS)"),
                dbc.CardBody([
                    html.Div(id="granger-results"),
                ]),
            ]),
        ], md=12),
    ], className="mb-4")


def create_anomaly_row() -> dbc.Row:
    """Create anomaly detection row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Anomaly Timeline"),
                dbc.CardBody([
                    dcc.Graph(id="anomaly-timeline", config={"displayModeBar": False}),
                ]),
            ]),
        ], md=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Active Alerts"),
                dbc.CardBody([
                    html.Div(id="active-alerts"),
                ]),
            ]),
        ], md=4),
    ], className="mb-4")


def create_chain_latency_row() -> dbc.Row:
    """Create latency chain analysis row."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Latency Chains"),
                dbc.CardBody([
                    html.Div(id="chain-latency"),
                ]),
            ]),
        ], md=12),
    ], className="mb-4")


def create_footer() -> html.Footer:
    """Create dashboard footer."""
    return html.Footer(
        dbc.Container([
            html.Hr(className="my-3"),
            html.P([
                "GPUGuard v0.1.0 | ",
                html.A("GitHub", href="https://github.com/darshan-stack/GPUGuard", target="_blank", className="text-decoration-none"),
                " | ",
                html.A("Documentation", href="/docs", className="text-decoration-none"),
            ], className="text-center text-muted small"),
        ]),
        className="mt-5",
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
            html.H2("GPU Metrics", id="gpu", className="mb-3 mt-4"),
            create_gpu_overview_row(),
            create_gpu_charts_row(),
            create_gpu_clocks_row(),

            # ROS 2 Section
            html.H2("ROS 2 Topics", id="ros", className="mb-3 mt-4"),
            create_ros_overview_row(),
            create_ros_details_row(),

            # Correlation Section
            html.H2("Correlation Analysis", id="corr", className="mb-3 mt-4"),
            create_correlation_row(),
            create_granger_row(),

            # Anomaly Section
            html.H2("Anomaly Detection", id="anomalies", className="mb-3 mt-4"),
            create_anomaly_row(),

            # Chain Latency
            html.H2("Latency Chains", id="chains", className="mb-3 mt-4"),
            create_chain_latency_row(),

            # Footer
            create_footer(),
        ], fluid=True, className="px-4"),

        # Interval for periodic updates (fallback)
        dcc.Interval(id="update-interval", interval=500, n_intervals=0),

        # Settings modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Settings")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Row([
                        dbc.Label("Update Interval (ms)", width=4),
                        dbc.Col([
                            dbc.Input(id="setting-update-interval", type="number", value=500, min=100, max=5000),
                        ], width=8),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Max Data Points", width=4),
                        dbc.Col([
                            dbc.Input(id="setting-max-points", type="number", value=500, min=100, max=5000),
                        ], width=8),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Theme", width=4),
                        dbc.Col([
                            dbc.Select(
                                id="setting-theme",
                                options=[
                                    {"label": "Dark", "value": "dark"},
                                    {"label": "Light", "value": "light"},
                                ],
                                value="dark",
                            ),
                        ], width=8),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Label("Correlation Threshold", width=4),
                        dbc.Col([
                            dbc.Input(id="setting-corr-threshold", type="number", value=0.5, min=0, max=1, step=0.1),
                        ], width=8),
                    ], className="mb-3"),
                ]),
            ]),
            dbc.ModalFooter([
                dbc.Button("Save", id="settings-save", color="primary"),
                dbc.Button("Cancel", id="settings-cancel", color="secondary"),
            ]),
        ], id="settings-modal", is_open=False),
    ])