"""Recommendation engine for GPUGuard diagnostics."""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

from gpuguard.anomaly.detector import Anomaly, AnomalyType, AnomalySeverity
from gpuguard.utils.logging import get_logger

logger = get_logger("diagnostic.recommendations")


class RecommendationCategory(str, Enum):
    """Categories of recommendations."""
    MODEL_OPTIMIZATION = "model_optimization"
    RESOURCE_MANAGEMENT = "resource_management"
    HARDWARE_CONFIG = "hardware_config"
    SOFTWARE_CONFIG = "software_config"
    SYSTEM_TUNING = "system_tuning"


@dataclass
class Recommendation:
    """Actionable recommendation."""
    category: RecommendationCategory
    title: str
    description: str
    priority: int  # 1=highest, 5=lowest
    effort: str  # "low", "medium", "high"
    impact: str  # "low", "medium", "high"
    commands: List[str] = None  # Shell commands to execute
    config_changes: Dict[str, Any] = None  # Config parameters to change

    def __post_init__(self):
        if self.commands is None:
            self.commands = []
        if self.config_changes is None:
            self.config_changes = {}


class RecommendationEngine:
    """Generates actionable recommendations based on anomalies and system state."""

    def __init__(self):
        self._rules = self._build_rules()

    def _build_rules(self) -> Dict[AnomalyType, List[Recommendation]]:
        """Build recommendation rules for each anomaly type."""
        return {
            AnomalyType.VRAM_PRESSURE: [
                Recommendation(
                    category=RecommendationCategory.MODEL_OPTIMIZATION,
                    title="Reduce YOLO batch size",
                    description="Lower batch size reduces VRAM usage during inference",
                    priority=1,
                    effort="low",
                    impact="high",
                    commands=["# Edit YOLO inference script: batch_size=1"],
                    config_changes={"yolo_batch_size": 1},
                ),
                Recommendation(
                    category=RecommendationCategory.MODEL_OPTIMIZATION,
                    title="Use smaller model variant",
                    description="Switch from YOLOv8m to YOLOv8n or YOLOv8s for lower VRAM",
                    priority=2,
                    effort="low",
                    impact="high",
                    config_changes={"yolo_model": "yolov8n"},
                ),
                Recommendation(
                    category=RecommendationCategory.MODEL_OPTIMIZATION,
                    title="Enable FP16/INT8 quantization",
                    description="Half-precision inference cuts VRAM usage by ~50%",
                    priority=2,
                    effort="medium",
                    impact="high",
                    commands=["pip install onnxruntime-gpu", "# Convert model to FP16 ONNX"],
                ),
                Recommendation(
                    category=RecommendationCategory.RESOURCE_MANAGEMENT,
                    title="Limit concurrent inference",
                    description="Run inference sequentially instead of in parallel",
                    priority=3,
                    effort="low",
                    impact="medium",
                ),
            ],
            AnomalyType.THERMAL_THROTTLING: [
                Recommendation(
                    category=RecommendationCategory.HARDWARE_CONFIG,
                    title="Improve GPU cooling",
                    description="Add better case fans, clean dust, or upgrade to liquid cooling",
                    priority=1,
                    effort="medium",
                    impact="high",
                ),
                Recommendation(
                    category=RecommendationCategory.SOFTWARE_CONFIG,
                    title="Set GPU power limit",
                    description="Reduce power limit to lower temperature at cost of performance",
                    priority=2,
                    effort="low",
                    impact="medium",
                    commands=["nvidia-smi -pl 200  # Set 200W limit (adjust for your GPU)"],
                ),
                Recommendation(
                    category=RecommendationCategory.MODEL_OPTIMIZATION,
                    title="Reduce inference frequency",
                    description="Lower YOLO inference rate from 30Hz to 15Hz",
                    priority=3,
                    effort="low",
                    impact="medium",
                    config_changes={"inference_rate_hz": 15},
                ),
                Recommendation(
                    category=RecommendationCategory.SYSTEM_TUNING,
                    title="Adjust fan curve",
                    description="Set aggressive fan curve via nvidia-settings or third-party tools",
                    priority=2,
                    effort="low",
                    impact="medium",
                    commands=["# Use nvidia-settings or MSI Afterburner to set custom fan curve"],
                ),
            ],
            AnomalyType.CLOCK_DROP: [
                Recommendation(
                    category=RecommendationCategory.SYSTEM_TUNING,
                    title="Disable GPU Boost",
                    description="Lock clocks to base frequency for consistent performance",
                    priority=1,
                    effort="low",
                    impact="high",
                    commands=["nvidia-smi -lgc 1500,1500  # Lock graphics clock (adjust for your GPU)"],
                ),
                Recommendation(
                    category=RecommendationCategory.HARDWARE_CONFIG,
                    title="Improve power delivery",
                    description="Ensure adequate PSU and PCIe power cables",
                    priority=2,
                    effort="high",
                    impact="medium",
                ),
            ],
            AnomalyType.POWER_THROTTLE: [
                Recommendation(
                    category=RecommendationCategory.SYSTEM_TUNING,
                    title="Increase power limit",
                    description="Raise power limit if thermal headroom exists",
                    priority=1,
                    effort="low",
                    impact="high",
                    commands=["nvidia-smi -pl 300  # Increase to 300W (adjust for your GPU)"],
                ),
                Recommendation(
                    category=RecommendationCategory.MODEL_OPTIMIZATION,
                    title="Optimize model efficiency",
                    description="Use TensorRT or ONNX Runtime for faster inference at lower power",
                    priority=2,
                    effort="medium",
                    impact="high",
                ),
            ],
            AnomalyType.LATENCY_SPIKE: [
                Recommendation(
                    category=RecommendationCategory.SOFTWARE_CONFIG,
                    title="Increase ROS 2 QoS depth",
                    description="Larger queue buffers absorb latency spikes",
                    priority=1,
                    effort="low",
                    impact="medium",
                    config_changes={"qos_depth": 50},
                ),
                Recommendation(
                    category=RecommendationCategory.SYSTEM_TUNING,
                    title="Pin ROS 2 threads to CPU cores",
                    description="Isolate inference and ROS threads on separate cores",
                    priority=2,
                    effort="medium",
                    impact="high",
                    commands=["# Use taskset or ROS 2 executor pinning"],
                ),
                Recommendation(
                    category=RecommendationCategory.RESOURCE_MANAGEMENT,
                    title="Add inference queue",
                    description="Buffer inference requests to smooth latency",
                    priority=3,
                    effort="medium",
                    impact="medium",
                ),
            ],
            AnomalyType.HZ_DROP: [
                Recommendation(
                    category=RecommendationCategory.SOFTWARE_CONFIG,
                    title="Check sensor driver",
                    description="Verify sensor is publishing at expected rate",
                    priority=1,
                    effort="low",
                    impact="high",
                ),
                Recommendation(
                    category=RecommendationCategory.RESOURCE_MANAGEMENT,
                    title="Reduce CPU load",
                    description="Offload non-critical processing or use ROS 2 component containers",
                    priority=2,
                    effort="medium",
                    impact="medium",
                ),
            ],
            AnomalyType.DEADLINE_MISS: [
                Recommendation(
                    category=RecommendationCategory.SYSTEM_TUNING,
                    title="Use ROS 2 real-time executor",
                    description="Switch to rclcpp real-time executor for deterministic scheduling",
                    priority=1,
                    effort="medium",
                    impact="high",
                    config_changes={"executor": "rclcpp::executors::SingleThreadedExecutor"},
                ),
                Recommendation(
                    category=RecommendationCategory.SOFTWARE_CONFIG,
                    title="Increase deadline threshold",
                    description="Relax deadline if occasional misses are acceptable",
                    priority=3,
                    effort="low",
                    impact="low",
                    config_changes={"deadline_ms": 100},
                ),
            ],
            AnomalyType.ECC_ERRORS: [
                Recommendation(
                    category=RecommendationCategory.HARDWARE_CONFIG,
                    title="Check GPU hardware",
                    description="ECC errors indicate potential GPU memory failure",
                    priority=1,
                    effort="high",
                    impact="critical",
                    commands=["# Run GPU memory diagnostic, consider RMA if persistent"],
                ),
                Recommendation(
                    category=RecommendationCategory.SYSTEM_TUNING,
                    title="Enable ECC error recovery",
                    description="Configure driver to handle correctable ECC errors",
                    priority=2,
                    effort="low",
                    impact="medium",
                ),
            ],
        }

    def generate_recommendations(self, anomalies: List[Anomaly],
                                  gpu_states: Dict, topic_stats: Dict) -> List[Recommendation]:
        """Generate recommendations based on anomalies and system state."""
        recommendations = []

        # Rule-based recommendations
        for anomaly in anomalies:
            rules = self._rules.get(anomaly.type, [])
            for rec in rules:
                # Customize based on context
                customized = self._customize_recommendation(rec, anomaly, gpu_states, topic_stats)
                recommendations.append(customized)

        # Cross-correlation recommendations
        cross_recs = self._generate_cross_recommendations(anomalies, gpu_states, topic_stats)
        recommendations.extend(cross_recs)

        # Deduplicate and sort
        unique_recs = self._deduplicate(recommendations)
        unique_recs.sort(key=lambda r: (r.priority, -{"high": 3, "medium": 2, "low": 1}[r.impact]))

        return unique_recs

    def _customize_recommendation(self, rec: Recommendation, anomaly: Anomaly,
                                   gpu_states: Dict, topic_stats: Dict) -> Recommendation:
        """Customize recommendation with specific values."""
        # Create copy with anomaly-specific details
        desc = rec.description
        if anomaly.gpu_metric and "gpu_id" in anomaly.__dict__:
            desc = f"{desc} (GPU {anomaly.gpu_id}: {anomaly.gpu_metric}={anomaly.value:.1f})"

        return Recommendation(
            category=rec.category,
            title=rec.title,
            description=desc,
            priority=rec.priority,
            effort=rec.effort,
            impact=rec.impact,
            commands=rec.commands.copy(),
            config_changes=rec.config_changes.copy(),
        )

    def _generate_cross_recommendations(self, anomalies: List[Anomaly],
                                         gpu_states: Dict, topic_stats: Dict) -> List[Recommendation]:
        """Generate recommendations from cross-analysis."""
        recs = []

        # GPU + ROS correlation patterns
        has_thermal = any(a.type == AnomalyType.THERMAL_THROTTLING for a in anomalies)
        has_latency = any(a.type == AnomalyType.LATENCY_SPIKE for a in anomalies)
        has_vram = any(a.type == AnomalyType.VRAM_PRESSURE for a in anomalies)
        has_deadline = any(a.type == AnomalyType.DEADLINE_MISS for a in anomalies)

        # Thermal + latency = GPU affecting ROS
        if has_thermal and has_latency:
            recs.append(Recommendation(
                category=RecommendationCategory.SYSTEM_TUNING,
                title="Isolate GPU and ROS workloads",
                description="Thermal throttling is causing ROS topic latency spikes. "
                            "Pin GPU inference and ROS nodes to separate CPU cores.",
                priority=1,
                effort="medium",
                impact="high",
                commands=[
                    "# Find CPU topology: lscpu",
                    "# Pin ROS nodes: taskset -c 0-3 ros2 run ...",
                    "# Pin inference: taskset -c 4-7 python inference.py",
                ],
            ))

        # VRAM + deadline misses
        if has_vram and has_deadline:
            recs.append(Recommendation(
                category=RecommendationCategory.RESOURCE_MANAGEMENT,
                title="Implement inference scheduling",
                description="VRAM pressure causing inference delays, leading to Nav2 deadline misses. "
                            "Add inference request queue with priority.",
                priority=1,
                effort="high",
                impact="high",
            ))

        # Check specific topic patterns
        for topic, stats in topic_stats.items():
            if "detection" in topic and stats.get("avg_latency_ms", 0) > 50:
                recs.append(Recommendation(
                    category=RecommendationCategory.MODEL_OPTIMIZATION,
                    title="Optimize detection pipeline",
                    description=f"Detection topic {topic} has high latency ({stats['avg_latency_ms']:.1f}ms). "
                                "Consider model distillation or ROI-based inference.",
                    priority=2,
                    effort="high",
                    impact="high",
                ))

        return recs

    def _deduplicate(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        """Remove duplicate recommendations."""
        seen = set()
        unique = []
        for rec in recommendations:
            key = (rec.title, rec.category)
            if key not in seen:
                seen.add(key)
                unique.append(rec)
        return unique


def create_recommendation_engine() -> RecommendationEngine:
    """Factory function."""
    return RecommendationEngine()