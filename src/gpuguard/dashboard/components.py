"""Reusable dashboard components."""
import dash_bootstrap_components as dbc
from dash import html, dcc
import plotly.graph_objs as go

# Peaceful light theme color palette
PEACEFUL_COLORS = {
    "primary": "#2563eb",      # Calm blue
    "success": "#059669",      # Gentle green
    "warning": "#d97706",      # Warm amber
    "danger": "#dc2626",       # Soft red
    "info": "#0891b2",         # Teal
    "purple": "#7c3aed",       # Muted purple
    "gray": "#64748b",         # Slate gray
    "bg": "#f8fafc",           # Light background
    "card_bg": "#ffffff",      # Card background
    "border": "#e2e8f0",       # Subtle borders
    "text_primary": "#1e293b", # Dark text
    "text_secondary": "#64748b", # Muted text
}


def create_metric_card(title: str, value: str, unit: str = "", color: str = "primary", icon: str = "") -> dbc.Card:
    """Create a metric display card."""
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Span(icon, className="me-2 fs-4") if icon else None,
                html.H6(title, className="text-muted mb-1"),
            ], className="d-flex align-items-center"),
            html.H2(f"{value} {unit}", className=f"text-{color} mb-0"),
        ])
    ], className="metric-card h-100")


def create_gauge_chart(value: float, max_value: float, title: str,
                       thresholds: list = None, unit: str = "") -> go.Figure:
    """Create a gauge chart with peaceful light theme."""
    if thresholds is None:
        thresholds = [
            (0, 50, "#059669"),   # success green
            (50, 80, "#d97706"),  # warning amber
            (80, 100, "#dc2626"), # danger red
        ]

    steps = []
    for low, high, color in thresholds:
        steps.append({"range": [low, high], "color": color})

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": f"{title} ({unit})", "font": {"size": 16, "color": "#1e293b"}},
        gauge={
            "axis": {"range": [0, max_value], "tickwidth": 1, "tickcolor": "#94a3b8"},
            "bar": {"color": "#2563eb"},
            "bgcolor": "#f1f5f9",
            "borderwidth": 1,
            "bordercolor": "#e2e8f0",
            "steps": steps,
            "threshold": {
                "line": {"color": "#dc2626", "width": 3},
                "thickness": 0.75,
                "value": max_value * 0.9,
            },
        },
    ))

    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#1e293b", "family": "Inter"},
    )
    return fig


def create_time_series_chart(data: list, x_key: str, y_keys: list,
                              title: str, y_title: str = "",
                              colors: list = None) -> go.Figure:
    """Create a time series chart with peaceful light theme."""
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False, font={"color": "#94a3b8", "size": 16})
        fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        return fig

    if colors is None:
        colors = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2"]

    fig = go.Figure()
    for i, y_key in enumerate(y_keys):
        y_values = [d.get(y_key, 0) for d in data]
        x_values = [d.get(x_key, 0) for d in data]
        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines",
            name=y_key.replace("_", " ").title(),
            line=dict(color=colors[i % len(colors)], width=2.5),
            hovertemplate=f"%{{y:.2f}} {y_title}<extra></extra>",
            fill="tozeroy",
            fillcolor=f"rgba({int(colors[i % len(colors)][1:3], 16)}, {int(colors[i % len(colors)][3:5], 16)}, {int(colors[i % len(colors)][5:7], 16)}, 0.1)",
        ))

    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#1e293b"}},
        xaxis_title="Time",
        yaxis_title=y_title,
        height=300,
        margin=dict(l=50, r=20, t=40, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#1e293b", "family": "Inter"},
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(255,255,255,0.8)"),
        xaxis=dict(
            gridcolor="#e2e8f0",
            zerolinecolor="#e2e8f0",
            showgrid=True,
        ),
        yaxis=dict(
            gridcolor="#e2e8f0",
            zerolinecolor="#e2e8f0",
            showgrid=True,
        ),
    )
    return fig


def create_time_series_chart(data: list, x_key: str, y_keys: list,
                              title: str, y_title: str = "",
                              colors: list = None) -> go.Figure:
    """Create a time series chart."""
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False, font={"color": "gray", "size": 16})
        fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        return fig

    if colors is None:
        colors = ["#00cc96", "#ef553b", "#636efa", "#ffa15a", "#ab63fa", "#19d3f3"]

    fig = go.Figure()
    for i, y_key in enumerate(y_keys):
        y_values = [d.get(y_key, 0) for d in data]
        x_values = [d.get(x_key, 0) for d in data]
        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines",
            name=y_key.replace("_", " ").title(),
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate=f"%{{y:.2f}} {y_title}<extra></extra>",
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title=y_title,
        height=300,
        margin=dict(l=50, r=20, t=40, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def create_correlation_heatmap(matrix: dict, title: str = "Correlation Matrix") -> go.Figure:
    """Create correlation heatmap with peaceful light theme."""
    if not matrix:
        fig = go.Figure()
        fig.add_annotation(text="No correlation data", xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False, font={"color": "#94a3b8", "size": 16})
        fig.update_layout(height=400, paper_bgcolor="rgba(0,0,0,0)")
        return fig

    gpu_metrics = list(matrix.keys())
    ros_topics = set()
    for metrics in matrix.values():
        ros_topics.update(metrics.keys())
    ros_topics = sorted(list(ros_topics))

    z = []
    for gpu_metric in gpu_metrics:
        row = []
        for ros_topic in ros_topics:
            row.append(matrix[gpu_metric].get(ros_topic, 0))
        z.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=[t.split("/")[-1] for t in ros_topics],
        y=[m.replace("_", " ").title() for m in gpu_metrics],
        colorscale="RdBu_r",
        zmid=0,
        zmin=-1,
        zmax=1,
        colorbar=dict(
            title="Correlation",
            titleside="right",
            titlefont={"color": "#1e293b"},
            tickfont={"color": "#64748b"},
        ),
        hovertemplate="GPU: %{y}<br>ROS: %{x}<br>Corr: %{z:.3f}<extra></extra>",
    ))

    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#1e293b"}},
        height=max(300, len(gpu_metrics) * 30 + 100),
        margin=dict(l=150, r=50, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#1e293b", "family": "Inter"},
        xaxis=dict(tickangle=45, tickfont={"color": "#64748b"}),
        yaxis=dict(tickfont={"color": "#64748b"}),
    )
    return fig


def create_anomaly_timeline(anomalies: list, title: str = "Anomaly Timeline") -> go.Figure:
    """Create anomaly timeline chart with peaceful light theme."""
    if not anomalies:
        fig = go.Figure()
        fig.add_annotation(text="No anomalies detected", xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False, font={"color": "#059669", "size": 16})
        fig.update_layout(height=200, paper_bgcolor="rgba(0,0,0,0)")
        return fig

    # Group by type
    types = {}
    for a in anomalies:
        t = a.get("type", "unknown")
        if t not in types:
            types[t] = []
        types[t].append(a)

    fig = go.Figure()
    colors = {
        "thermal": "#dc2626",
        "vram": "#d97706",
        "clock": "#7c3aed",
        "power": "#0891b2",
        "latency": "#059669",
        "ecc": "#ef4444",
        "hz_drop": "#f59e0b",
        "deadline": "#dc2626",
        "isolation_forest": "#636efa",
    }

    for i, (atype, items) in enumerate(types.items()):
        times = [a.get("timestamp", 0) / 1e9 for a in items]
        values = [a.get("value", 0) for a in items]
        messages = [a.get("message", "") for a in items]

        fig.add_trace(go.Scatter(
            x=times,
            y=[i] * len(items),
            mode="markers",
            marker=dict(
                size=14,
                color=colors.get(atype, "#64748b"),
                symbol="diamond",
                line=dict(width=2, color="#ffffff"),
            ),
            name=atype.replace("_", " ").title(),
            text=messages,
            hovertemplate="%{text}<br>Value: %{customdata[0]:.1f}<extra></extra>",
            customdata=list(zip(values)),
        ))

    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#1e293b"}},
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(len(types))),
            ticktext=[t.replace("_", " ").title() for t in types.keys()],
            tickfont={"color": "#64748b"},
        ),
        height=200,
        margin=dict(l=100, r=20, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#1e293b", "family": "Inter"},
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)",
            font={"color": "#1e293b"},
        ),
    )
    return fig


def create_topic_hz_chart(topics_data: dict, title: str = "Topic Rates") -> go.Figure:
    """Create topic Hz bar chart with peaceful light theme."""
    if not topics_data:
        fig = go.Figure()
        fig.add_annotation(text="No topic data", xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False, font={"color": "#94a3b8", "size": 16})
        fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)")
        return fig

    topics = list(topics_data.keys())
    current_hz = [topics_data[t].get("current_hz", 0) for t in topics]
    avg_hz = [topics_data[t].get("avg_hz", 0) for t in topics]
    expected_hz = [topics_data[t].get("expected_hz", 0) for t in topics]

    short_names = [t.split("/")[-1] for t in topics]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Current", x=short_names, y=current_hz,
        marker_color="#2563eb",
        marker_line_color="#1d4ed8",
        marker_line_width=1,
    ))
    fig.add_trace(go.Bar(
        name="Average", x=short_names, y=avg_hz,
        marker_color="#059669",
        marker_line_color="#047857",
        marker_line_width=1,
    ))
    if any(e > 0 for e in expected_hz):
        fig.add_trace(go.Bar(
            name="Expected", x=short_names, y=expected_hz,
            marker_color="#d97706",
            opacity=0.6,
            marker_line_color="#b45309",
            marker_line_width=1,
        ))

    fig.update_layout(
        title={"text": title, "font": {"size": 14, "color": "#1e293b"}},
        barmode="group",
        xaxis_title="Topic",
        yaxis_title="Hz",
        height=300,
        margin=dict(l=50, r=20, t=40, b=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#1e293b", "family": "Inter"},
        xaxis=dict(
            tickangle=45,
            gridcolor="#e2e8f0",
            tickfont={"color": "#64748b"},
        ),
        yaxis=dict(
            gridcolor="#e2e8f0",
            tickfont={"color": "#64748b"},
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)",
            font={"color": "#1e293b"},
        ),
    )
    return fig