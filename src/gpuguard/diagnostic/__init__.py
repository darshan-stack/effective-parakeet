"""AI Diagnostic Engine package."""
from gpuguard.diagnostic.ai_diagnostic import AIDiagnosticEngine, Diagnosis, create_diagnostic_engine
from gpuguard.diagnostic.recommendation_engine import RecommendationEngine, Recommendation, RecommendationCategory, create_recommendation_engine
from gpuguard.diagnostic.prompt_templates import (
    SYSTEM_PROMPT_V1,
    DIAGNOSTIC_PROMPT_TEMPLATE,
    build_diagnostic_prompt,
    format_anomalies,
    format_gpu_states,
    format_topic_stats,
    format_correlations,
    get_system_prompt,
)

__all__ = [
    "AIDiagnosticEngine",
    "Diagnosis",
    "create_diagnostic_engine",
    "RecommendationEngine",
    "Recommendation",
    "RecommendationCategory",
    "create_recommendation_engine",
    "SYSTEM_PROMPT_V1",
    "DIAGNOSTIC_PROMPT_TEMPLATE",
    "build_diagnostic_prompt",
    "format_anomalies",
    "format_gpu_states",
    "format_topic_stats",
    "format_correlations",
    "get_system_prompt",
]