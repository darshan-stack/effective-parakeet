"""Prompt templates for AI diagnostic engine."""
from typing import Dict, List


SYSTEM_PROMPT_V1 = """You are GPUGuard, an expert AI diagnostician for GPU-accelerated robotics systems.
Your role is to analyze GPU telemetry, ROS 2 topic performance, and correlation data to identify root causes of performance issues and provide actionable recommendations.

Key domains:
- NVIDIA GPU architecture (VRAM, compute, thermal, power, clocks)
- ROS 2 real-time performance (topic rates, latency, deadline misses)
- Physical AI robotics (YOLO inference, Nav2 navigation, sensor pipelines)
- System-level interactions (GPU-CPU contention, PCIe bandwidth, thermal throttling)

Response format (JSON):
{
  "root_cause": "One-sentence root cause summary",
  "explanation": "Detailed technical explanation (2-3 sentences)",
  "recommendations": ["Specific action 1", "Specific action 2", "Specific action 3"],
  "confidence": 0.0-1.0
}

Be specific, actionable, and technically accurate. Reference actual metrics and thresholds."""


DIAGNOSTIC_PROMPT_TEMPLATE = """## GPUGuard Diagnostic Request

### Active Anomalies
{anomalies}

### GPU States
{gpu_states}

### ROS 2 Topic Performance
{topic_stats}

### Significant Correlations (|r| > 0.5)
{correlations}

---
Provide diagnosis in JSON format as specified."""


def format_anomalies(anomalies: List[Dict]) -> str:
    """Format anomalies for prompt."""
    if not anomalies:
        return "None"

    lines = []
    for a in anomalies:
        severity_marker = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(a.get('severity', 'info'), '⚪')
        lines.append(f"{severity_marker} **{a.get('type', 'unknown').upper()}** ({a.get('severity', 'info')}): {a.get('message', '')}")
        if a.get('gpu_metric'):
            lines.append(f"  GPU Metric: {a['gpu_metric']} = {a.get('value', 0):.1f} (threshold: {a.get('threshold', 0):.1f})")
        if a.get('ros_topic'):
            lines.append(f"  ROS Topic: {a['ros_topic']}")
    return "\n".join(lines)


def format_gpu_states(gpu_states: Dict) -> str:
    """Format GPU states for prompt."""
    if not gpu_states:
        return "No GPU data available"

    lines = []
    for gpu_id, state in gpu_states.items():
        lines.append(f"\n**GPU {gpu_id}** ({state.get('name', 'Unknown')}):")
        lines.append(f"- VRAM: {state.get('memory_used_pct', 0):.1f}% ({state.get('memory_used', 0)/1e9:.1f}/{state.get('memory_total', 0)/1e9:.1f} GB)")
        lines.append(f"- GPU Util: {state.get('utilization_gpu', 0):.1f}%")
        lines.append(f"- Memory Util: {state.get('utilization_memory', 0):.1f}%")
        lines.append(f"- Temp: {state.get('temperature_gpu', 0):.1f}°C")
        lines.append(f"- Power: {state.get('power_draw', 0):.1f}W / {state.get('power_limit', 0):.1f}W ({state.get('power_draw_pct', 0):.1f}%)")
        lines.append(f"- Clocks: Graphics={state.get('clock_graphics', 0)}MHz, SM={state.get('clock_sm', 0)}MHz, Mem={state.get('clock_mem', 0)}MHz")
        lines.append(f"- Fan: {state.get('fan_speed', 0):.1f}%")
        lines.append(f"- Throttling: {state.get('is_throttling', False)}")
        if state.get('ecc_errors_volatile', 0) > 0:
            lines.append(f"- ECC Errors: {state['ecc_errors_volatile']}")
    return "\n".join(lines)


def format_topic_stats(topic_stats: Dict) -> str:
    """Format topic stats for prompt."""
    if not topic_stats:
        return "No ROS 2 topic data available"

    lines = []
    for topic, stats in topic_stats.items():
        lines.append(f"\n**{topic}** ({stats.get('message_type', 'unknown')}):")
        lines.append(f"- Rate: {stats.get('current_hz', 0):.1f}Hz (avg: {stats.get('avg_hz', 0):.1f}Hz)")
        lines.append(f"- Latency: avg={stats.get('avg_latency_ms', 0):.1f}ms, P99={stats.get('p99_latency_ms', 0):.1f}ms")
        lines.append(f"- Deadline: {stats.get('deadline_ms', 0):.1f}ms, Misses: {stats.get('deadline_misses', 0)}")
        if stats.get('consecutive_misses', 0) > 0:
            lines.append(f"- ⚠️ Consecutive misses: {stats['consecutive_misses']}")
    return "\n".join(lines)


def format_correlations(correlations: List[Dict]) -> str:
    """Format correlations for prompt."""
    sig_corrs = [c for c in correlations if c.get('significant', False) and abs(c.get('correlation', 0)) >= 0.5]
    if not sig_corrs:
        return "No significant correlations detected"

    lines = []
    for c in sig_corrs:
        lines.append(f"- {c['gpu_metric']} ↔ {c['ros_topic']}: r={c['correlation']:.3f} (lag={c['lag_ms']:.1f}ms, p={c['p_value']:.4f})")
    return "\n".join(lines)


def build_diagnostic_prompt(anomalies: List[Dict], gpu_states: Dict,
                            topic_stats: Dict, correlations: List[Dict]) -> str:
    """Build complete diagnostic prompt."""
    return DIAGNOSTIC_PROMPT_TEMPLATE.format(
        anomalies=format_anomalies(anomalies),
        gpu_states=format_gpu_states(gpu_states),
        topic_stats=format_topic_stats(topic_stats),
        correlations=format_correlations(correlations),
    )


PROMPT_VERSIONS = {
    "v1": SYSTEM_PROMPT_V1,
}


def get_system_prompt(version: str = "v1") -> str:
    """Get system prompt by version."""
    return PROMPT_VERSIONS.get(version, SYSTEM_PROMPT_V1)