"""AI Diagnostic Engine using Claude API."""
import os
import json
import time
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from functools import lru_cache

from gpuguard.utils.config import get_config, AIDiagnosticConfig
from gpuguard.utils.logging import get_logger

logger = get_logger("diagnostic.ai")


@dataclass
class Diagnosis:
    """AI diagnosis result."""
    timestamp_ns: int
    root_cause: str
    explanation: str
    recommendations: List[str]
    confidence: float
    anomalies_analyzed: List[Dict]
    model: str
    tokens_used: int = 0


class AIDiagnosticEngine:
    """AI-powered diagnostic engine using Anthropic Claude API."""

    def __init__(self, config: Optional[AIDiagnosticConfig] = None):
        self.config = config or get_config().ai_diagnostic
        self._cache: Dict[str, Diagnosis] = {}
        self._client = None

        # Initialize Anthropic client if enabled
        if self.config.enabled:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize Anthropic client."""
        try:
            import anthropic
            api_key = os.environ.get(self.config.api_key_env)
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)
                logger.info("AI Diagnostic Engine initialized with Claude API")
            else:
                logger.warning(f"API key not found in {self.config.api_key_env}, AI diagnostics disabled")
                self.config.enabled = False
        except ImportError:
            logger.warning("anthropic package not installed, AI diagnostics disabled")
            self.config.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            self.config.enabled = False

    def diagnose(self, anomalies: List[Dict], gpu_states: Dict, topic_stats: Dict,
                 correlations: List[Dict]) -> Optional[Diagnosis]:
        """Generate diagnosis from anomalies and system state."""
        if not self.config.enabled or not self._client:
            return None

        # Create cache key
        cache_key = self._make_cache_key(anomalies, gpu_states, topic_stats, correlations)

        # Check cache
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time_ns() - cached.timestamp_ns < self.config.cache_ttl_s * 1e9:
                logger.debug("Returning cached diagnosis")
                return cached

        # Build prompt
        prompt = self._build_prompt(anomalies, gpu_states, topic_stats, correlations)

        # Call Claude API
        try:
            response = self._client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            diagnosis = self._parse_response(response, anomalies)

            # Cache result
            self._cache[cache_key] = diagnosis

            return diagnosis

        except Exception as e:
            logger.error(f"AI diagnosis failed: {e}")
            return None

    def _make_cache_key(self, anomalies: List[Dict], gpu_states: Dict,
                        topic_stats: Dict, correlations: List[Dict]) -> str:
        """Create cache key from input data."""
        data = {
            "anomalies": [(a.get("type"), a.get("gpu_metric"), a.get("ros_topic"), a.get("severity")) for a in anomalies],
            "gpu_states": {k: {mk: round(mv, 1) for mk, mv in v.items() if isinstance(mv, (int, float))} for k, v in gpu_states.items()},
            "topic_stats": {k: {mk: round(mv, 1) for mk, mv in v.items() if isinstance(mv, (int, float))} for k, v in topic_stats.items()},
            "correlations": [(c.get("gpu_metric"), c.get("ros_topic"), round(c.get("correlation", 0), 2)) for c in correlations],
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _get_system_prompt(self) -> str:
        """Get system prompt for diagnosis."""
        return """You are GPUGuard, an expert AI diagnostician for GPU-accelerated robotics systems.
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

    def _build_prompt(self, anomalies: List[Dict], gpu_states: Dict,
                      topic_stats: Dict, correlations: List[Dict]) -> str:
        """Build diagnostic prompt."""
        lines = ["## GPUGuard Diagnostic Request\n"]

        # Anomalies
        if anomalies:
            lines.append("### Active Anomalies")
            for a in anomalies:
                lines.append(f"- **{a.get('type', 'unknown').upper()}** ({a.get('severity', 'info')}): {a.get('message', '')}")
                if a.get('gpu_metric'):
                    lines.append(f"  GPU Metric: {a['gpu_metric']} = {a.get('value', 0):.1f} (threshold: {a.get('threshold', 0):.1f})")
                if a.get('ros_topic'):
                    lines.append(f"  ROS Topic: {a['ros_topic']}")

        # GPU States
        if gpu_states:
            lines.append("\n### GPU States")
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

        # Topic Stats
        if topic_stats:
            lines.append("\n### ROS 2 Topic Performance")
            for topic, stats in topic_stats.items():
                lines.append(f"\n**{topic}** ({stats.get('message_type', 'unknown')}):")
                lines.append(f"- Rate: {stats.get('current_hz', 0):.1f}Hz (avg: {stats.get('avg_hz', 0):.1f}Hz)")
                lines.append(f"- Latency: avg={stats.get('avg_latency_ms', 0):.1f}ms, P99={stats.get('p99_latency_ms', 0):.1f}ms")
                lines.append(f"- Deadline: {stats.get('deadline_ms', 0):.1f}ms, Misses: {stats.get('deadline_misses', 0)}")
                if stats.get('consecutive_misses', 0) > 0:
                    lines.append(f"- ⚠️ Consecutive misses: {stats['consecutive_misses']}")

        # Correlations
        if correlations:
            lines.append("\n### Significant Correlations (|r| > 0.5)")
            for c in correlations:
                if c.get('significant', False) and abs(c.get('correlation', 0)) >= 0.5:
                    lines.append(f"- {c['gpu_metric']} ↔ {c['ros_topic']}: r={c['correlation']:.3f} (lag={c['lag_ms']:.1f}ms, p={c['p_value']:.4f})")

        lines.append("\n---\nProvide diagnosis in JSON format as specified.")

        return "\n".join(lines)

    def _parse_response(self, response, anomalies: List[Dict]) -> Diagnosis:
        """Parse Claude response into Diagnosis."""
        import anthropic

        content = response.content[0].text if response.content else "{}"

        try:
            # Extract JSON from response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
            else:
                raise ValueError("No JSON found in response")

            return Diagnosis(
                timestamp_ns=time.time_ns(),
                root_cause=data.get("root_cause", "Unknown"),
                explanation=data.get("explanation", ""),
                recommendations=data.get("recommendations", []),
                confidence=data.get("confidence", 0.5),
                anomalies_analyzed=anomalies,
                model=self.config.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
            )
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            return Diagnosis(
                timestamp_ns=time.time_ns(),
                root_cause="AI parsing error",
                explanation=f"Failed to parse AI response: {e}",
                recommendations=["Check AI diagnostic logs"],
                confidence=0.0,
                anomalies_analyzed=anomalies,
                model=self.config.model,
            )

    def clear_cache(self) -> None:
        """Clear diagnosis cache."""
        self._cache.clear()


def create_diagnostic_engine(config: Optional[AIDiagnosticConfig] = None) -> AIDiagnosticEngine:
    """Factory function to create diagnostic engine."""
    return AIDiagnosticEngine(config)