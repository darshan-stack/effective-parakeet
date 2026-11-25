"""Dashboard callbacks for real-time updates."""
from dash import Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc
from dash import html
import json
import asyncio
import websockets
from typing import Dict, List, Any
import threading
import time

from gpuguard.dashboard.components import (
    create_gauge_chart,
    create_time_series_chart,
    create_correlation_heatmap,
    create_anomaly_timeline,
    create_topic_hz_chart,
)
from gpuguard.utils.logging import get_logger

logger = get_logger("dashboard.callbacks")

# Global data stores (updated by WebSocket thread)
_dashboard_data = {
    "gpu_states": {},
    "gpu_infos": {},
    "topic_stats": {},
    "correlations": [],
    "granger_results": [],
    "anomalies": [],
    "chain_latencies": {},
}
_data_lock = threading.Lock()


def register_callbacks(app):
    """Register all dashboard callbacks."""

    @app.callback(
        Output("gpu-util-value", "children"),
        Output("vram-value", "children"),
        Output("vram-detail", "children"),
        Output("temp-value", "children"),
        Output("temp-detail", "children"),
        Output("power-value", "children"),
        Output("power-detail", "children"),
        Input("update-interval", "n_intervals"),
    )
    def update_gpu_overview(n):
        with _data_lock:
            gpu_states = _dashboard_data["gpu_states"]

        if not gpu_states:
            return "—", "—", "", "—", "", "—", ""

        # Use first GPU
        gpu_id = list(gpu_states.keys())[0]
        state = gpu_states[gpu_id]

        util = f"{state.get('utilization_gpu', 0):.1f}%"
        vram = f"{state.get('memory_used_pct', 0):.1f}%"
        vram_detail = f"{state.get('memory_used', 0) / 1e9:.1f} / {state.get('memory_total', 0) / 1e9:.1f} GB"
        temp = f"{state.get('temperature_gpu', 0):.1f}°C"
        temp_detail = "⚠️ Throttling!" if state.get('is_throttling') else "Normal"
        power = f"{state.get('power_draw', 0):.1f}W"
        power_detail = f"{state.get('power_draw_pct', 0):.0f}% of limit"

        return util, vram, vram_detail, temp, temp_detail, power, power_detail

    @app.callback(
        Output("gpu-util-chart", "figure"),
        Input("update-interval", "n_intervals"),
    )
    def update_gpu_util_chart(n):
        with _data_lock:
            gpu_states = _dashboard_data["gpu_states"]

        if not gpu_states:
            return create_time_series_chart([], "timestamp", [], "No Data")

        gpu_id = list(gpu_states.keys())[0]
        # In a real app, we'd store history; for now create sample from current state
        # This is a placeholder - real implementation would use historical data store
        return create_time_series_chart(
            [{"timestamp": 0, "utilization_gpu": 0}],
            "timestamp", ["utilization_gpu"],
            "GPU Utilization History", "%",
        )

    @app.callback(
        Output("gpu-temp-power-chart", "figure"),
        Input("update-interval", "n_intervals"),
    )
    def update_temp_power_chart(n):
        return create_time_series_chart(
            [], "timestamp", ["temperature_gpu", "power_draw"],
            "Temperature & Power", "°C / W",
        )

    @app.callback(
        Output("gpu-clocks-chart", "figure"),
        Input("update-interval", "n_intervals"),
    )
    def update_clocks_chart(n):
        return create_time_series_chart(
            [], "timestamp", ["clock_graphics", "clock_sm", "clock_mem"],
            "GPU Clock Frequencies", "MHz",
        )

    @app.callback(
        Output("ros-hz-chart", "figure"),
        Input("update-interval", "n_intervals"),
    )
    def update_ros_hz_chart(n):
        with _data_lock:
            topic_stats = _dashboard_data["topic_stats"]

        if not topic_stats:
            return create_topic_hz_chart({})

        # Prepare data for chart
        chart_data = {}
        for topic, stats in topic_stats.items():
            chart_data[topic] = {
                "current_hz": stats.get("current_hz", 0),
                "avg_hz": stats.get("avg_hz", 0),
                "expected_hz": 1000 / stats.get("deadline_ms", 50) if stats.get("deadline_ms") else 0,
            }

        return create_topic_hz_chart(chart_data)

    @app.callback(
        Output("ros-latency-chart", "figure"),
        Input("update-interval", "n_intervals"),
    )
    def update_ros_latency_chart(n):
        with _data_lock:
            topic_stats = _dashboard_data["topic_stats"]

        if not topic_stats:
            return create_time_series_chart([], "timestamp", [], "No Latency Data")

        # Create latency bar chart
        topics = list(topic_stats.keys())
        p50 = [topic_stats[t].get("p50_latency_ms", 0) for t in topics]
        p95 = [topic_stats[t].get("p95_latency_ms", 0) for t in topics]
        p99 = [topic_stats[t].get("p99_latency_ms", 0) for t in topics]

        import plotly.graph_objs as go
        fig = go.Figure()
        fig.add_trace(go.Bar(name="P50", x=[t.split("/")[-1] for t in topics], y=p50, marker_color="#00cc96"))
        fig.add_trace(go.Bar(name="P95", x=[t.split("/")[-1] for t in topics], y=p95, marker_color="#ffa15a"))
        fig.add_trace(go.Bar(name="P99", x=[t.split("/")[-1] for t in topics], y=p99, marker_color="#ef553b"))

        fig.update_layout(
            title="Topic Latency Percentiles",
            barmode="group",
            xaxis_title="Topic",
            yaxis_title="Latency (ms)",
            height=300,
            margin=dict(l=50, r=20, t=40, b=80),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "white"},
            xaxis=dict(tickangle=45),
        )
        return fig

    @app.callback(
        Output("ros-topic-table", "children"),
        Input("update-interval", "n_intervals"),
    )
    def update_ros_topic_table(n):
        with _data_lock:
            topic_stats = _dashboard_data["topic_stats"]

        if not topic_stats:
            return html.P("No topic data available", className="text-muted text-center")

        rows = []
        for topic, stats in topic_stats.items():
            deadline_misses = stats.get("consecutive_misses", 0)
            miss_color = "danger" if deadline_misses > 0 else "success"

            rows.append(html.Tr([
                html.Td(topic, className="font-monospace small"),
                html.Td(stats.get("message_type", "unknown"), className="small"),
                html.Td(f"{stats.get('current_hz', 0):.1f}", className="small"),
                html.Td(f"{stats.get('avg_hz', 0):.1f}", className="small"),
                html.Td(f"{stats.get('avg_latency_ms', 0):.2f}", className="small"),
                html.Td(f"{stats.get('p99_latency_ms', 0):.2f}", className="small"),
                html.Td(
                    dbc.Badge(str(deadline_misses), color=miss_color, className="ms-1"),
                    className="text-center",
                ),
            ]))

        return dbc.Table([
            html.Thead(html.Tr([
                html.Th("Topic"), html.Th("Type"), html.Th("Current Hz"),
                html.Th("Avg Hz"), html.Th("Avg Latency"), html.Th("P99 Latency"),
                html.Th("Misses"),
            ])),
            html.Tbody(rows),
        ], bordered=True, hover=True, responsive=True, striped=True, size="sm")

    @app.callback(
        Output("correlation-heatmap", "figure"),
        Input("update-interval", "n_intervals"),
    )
    def update_correlation_heatmap(n):
        with _data_lock:
            correlations = _dashboard_data["correlations"]

        # Build matrix
        matrix = {}
        for corr in correlations:
            gpu_metric = corr.get("gpu_metric", "")
            ros_topic = corr.get("ros_topic", "")
            corr_val = corr.get("correlation", 0)

            if gpu_metric not in matrix:
                matrix[gpu_metric] = {}
            matrix[gpu_metric][ros_topic] = corr_val

        return create_correlation_heatmap(matrix)

    @app.callback(
        Output("significant-correlations", "children"),
        Input("update-interval", "n_intervals"),
    )
    def update_significant_correlations(n):
        with _data_lock:
            correlations = _dashboard_data["correlations"]

        sig_corrs = [c for c in correlations if c.get("significant", False) and abs(c.get("correlation", 0)) >= 0.5]

        if not sig_corrs:
            return html.P("No significant correlations detected", className="text-muted text-center")

        items = []
        for corr in sorted(sig_corrs, key=lambda x: abs(x.get("correlation", 0)), reverse=True)[:10]:
            corr_val = corr.get("correlation", 0)
            color = "success" if corr_val > 0 else "danger"
            items.append(dbc.ListGroupItem([
                html.Div([
                    html.Strong(f"{corr.get('gpu_metric', '')} → {corr.get('ros_topic', '')}"),
                    html.Small(f" (lag: {corr.get('lag_ms', 0):.1f}ms)", className="text-muted ms-2"),
                ]),
                dbc.Badge(f"{corr_val:.3f}", color=color, className="ms-auto"),
            ], className="d-flex justify-content-between align-items-center"))

        return dbc.ListGroup(items, flush=True)

    @app.callback(
        Output("granger-results", "children"),
        Input("update-interval", "n_intervals"),
    )
    def update_granger_results(n):
        with _data_lock:
            granger = _dashboard_data["granger_results"]

        if not granger:
            return html.P("Computing Granger causality...", className="text-muted text-center")

        causal = [g for g in granger if g.get("causes_ros", False)]

        if not causal:
            return html.P("No Granger causality detected", className="text-muted text-center")

        items = []
        for g in sorted(causal, key=lambda x: x.get("p_value", 1))[:10]:
            items.append(dbc.ListGroupItem([
                html.Div([
                    html.Strong(f"{g.get('gpu_metric', '')} → {g.get('ros_topic', '')}"),
                    html.Small(f" (lag: {g.get('optimal_lag', 0)}, p={g.get('p_value', 0):.4f})", className="text-muted ms-2"),
                ]),
                dbc.Badge("CAUSAL", color="warning", className="ms-auto"),
            ], className="d-flex justify-content-between align-items-center"))

        return dbc.ListGroup(items, flush=True)

    @app.callback(
        Output("anomaly-timeline", "figure"),
        Input("update-interval", "n_intervals"),
    )
    def update_anomaly_timeline(n):
        with _data_lock:
            anomalies = _dashboard_data["anomalies"]

        return create_anomaly_timeline(anomalies)

    @app.callback(
        Output("active-alerts", "children"),
        Input("update-interval", "n_intervals"),
    )
    def update_active_alerts(n):
        with _data_lock:
            anomalies = _dashboard_data["anomalies"]

        # Get recent anomalies (last 60 seconds)
        import time
        now = time.time()
        recent = [a for a in anomalies if now - a.get("timestamp", 0) < 60]

        if not recent:
            return html.Div([
                dbc.Alert("No active alerts", color="success", className="text-center"),
            ])

        alerts = []
        for a in sorted(recent, key=lambda x: x.get("timestamp", 0), reverse=True)[:10]:
            severity = a.get("severity", "warning")
            color = {"critical": "danger", "warning": "warning", "info": "info"}.get(severity, "warning")

            alerts.append(dbc.Alert([
                html.Div([
                    html.Strong(a.get("type", "Unknown").title()),
                    html.Small(f" - {a.get('gpu_metric', '') or a.get('ros_topic', '')}", className="text-muted ms-2"),
                ]),
                html.P(a.get("message", ""), className="mb-1 small"),
                html.Small(f"Value: {a.get('value', 0):.1f} (threshold: {a.get('threshold', 0):.1f})", className="text-muted"),
            ], color=color, className="py-2"))

        return html.Div(alerts)

    @app.callback(
        Output("chain-latency", "children"),
        Input("update-interval", "n_intervals"),
    )
    def update_chain_latency(n):
        with _data_lock:
            chains = _dashboard_data["chain_latencies"]

        if not chains:
            return html.P("No chain latency data", className="text-muted text-center")

        items = []
        for chain_name, data in chains.items():
            topics = data.get("topics", {})
            if not topics:
                continue

            topic_items = []
            for topic, lat in topics.items():
                topic_items.append(dbc.ListGroupItem([
                    html.Span(topic.split("/")[-1], className="font-monospace small me-2"),
                    html.Span(f"avg: {lat.get('avg_ms', 0):.1f}ms", className="text-success small me-2"),
                    html.Span(f"max: {lat.get('max_ms', 0):.1f}ms", className="text-warning small"),
                ], className="d-flex justify-content-between"))

            items.append(html.Div([
                html.H6(chain_name.title(), className="mb-2"),
                dbc.ListGroup(topic_items, flush=True),
            ], className="mb-3"))

        return html.Div(items)

    # Settings modal
    @app.callback(
        Output("settings-modal", "is_open"),
        Input("settings-btn", "n_clicks"),
        Input("settings-save", "n_clicks"),
        Input("settings-cancel", "n_clicks"),
        State("settings-modal", "is_open"),
    )
    def toggle_settings_modal(open_clicks, save_clicks, cancel_clicks, is_open):
        ctx = callback_context
        if not ctx.triggered:
            return is_open
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if button_id in ["settings-btn", "settings-cancel"]:
            return not is_open
        if button_id == "settings-save":
            return False
        return is_open


# Data update functions (called from WebSocket thread)
def update_gpu_state(gpu_id: int, state: Dict[str, Any]):
    """Update GPU state from collector."""
    with _data_lock:
        _dashboard_data["gpu_states"][gpu_id] = state


def update_gpu_info(gpu_id: int, info: Dict[str, Any]):
    """Update GPU info."""
    with _data_lock:
        _dashboard_data["gpu_infos"][gpu_id] = info


def update_topic_stats(topic: str, stats: Dict[str, Any]):
    """Update topic statistics."""
    with _data_lock:
        _dashboard_data["topic_stats"][topic] = stats


def update_correlations(correlations: List[Dict[str, Any]]):
    """Update correlation results."""
    with _data_lock:
        _dashboard_data["correlations"] = correlations


def update_granger_results(results: List[Dict[str, Any]]):
    """Update Granger causality results."""
    with _data_lock:
        _dashboard_data["granger_results"] = results


def update_anomalies(anomalies: List[Dict[str, Any]]):
    """Update anomaly list."""
    with _data_lock:
        _dashboard_data["anomalies"] = anomalies


def update_chain_latency(chain_name: str, data: Dict[str, Any]):
    """Update chain latency."""
    with _data_lock:
        _dashboard_data["chain_latencies"][chain_name] = data