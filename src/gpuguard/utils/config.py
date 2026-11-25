"""Configuration management for GPUGuard."""
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectorConfig(BaseModel):
    poll_interval_ms: int = 100
    gpu_indices: list[int] = Field(default_factory=lambda: [0])
    metrics: list[str] = Field(default_factory=list)
    buffer_size: int = 10000
    export_interval_s: int = 10


class MonitorConfig(BaseModel):
    topics: list[str] = Field(default_factory=list)
    deadline_ms: int = 50
    window_size: int = 100
    hz_window_s: float = 5.0
    latency_percentiles: list[int] = Field(default_factory=lambda: [50, 90, 95, 99])
    qos_depth: int = 10


class CorrelationConfig(BaseModel):
    sync_tolerance_ms: int = 5
    min_samples: int = 50
    granger_maxlag: int = 10
    correlation_method: str = "pearson"
    significance_level: float = 0.05
    rolling_window: int = 200


class AnomalyConfig(BaseModel):
    vram_threshold_pct: float = 85.0
    temp_threshold_c: float = 80.0
    temp_critical_c: float = 85.0
    clock_drop_threshold_pct: float = 15.0
    power_throttle_threshold_pct: float = 90.0
    latency_spike_threshold: float = 3.0
    hz_drop_threshold_pct: float = 30.0
    deadline_miss_threshold: int = 3
    ecc_error_threshold: int = 0
    isolation_forest_contamination: float = 0.05
    isolation_forest_n_estimators: int = 100


class AIDiagnosticConfig(BaseModel):
    enabled: bool = True
    api_key_env: str = "ANTHROPIC_API_KEY"
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 1500
    temperature: float = 0.1
    timeout_s: int = 30
    cache_ttl_s: int = 300
    prompt_version: str = "v1"


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    ws_port: int = 8081
    cors_origins: list[str] = Field(default_factory=list)
    rate_limit: int = 100
    enable_metrics: bool = True


class DashboardConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8050
    update_interval_ms: int = 500
    max_data_points: int = 500
    theme: str = "dark"
    charts: Dict[str, bool] = Field(default_factory=dict)


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/gpuguard.log"
    max_size_mb: int = 100
    backup_count: int = 5
    include_ros_logs: bool = False


class ROS2Config(BaseModel):
    domain_id: int = 0
    node_name: str = "gpuguard_monitor"
    namespace: str = ""
    use_sim_time: bool = False
    qos_reliability: str = "reliable"
    qos_durability: str = "volatile"


class GPUGuardConfig(BaseModel):
    collector: CollectorConfig = Field(default_factory=CollectorConfig)
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    correlation: CorrelationConfig = Field(default_factory=CorrelationConfig)
    anomaly: AnomalyConfig = Field(default_factory=AnomalyConfig)
    ai_diagnostic: AIDiagnosticConfig = Field(default_factory=AIDiagnosticConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    ros2: ROS2Config = Field(default_factory=ROS2Config)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPUGUARD_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    config_file: Optional[str] = None
    collector__poll_interval_ms: Optional[int] = None
    collector__gpu_indices: Optional[str] = None  # Comma-separated
    monitor__topics: Optional[str] = None  # Comma-separated
    monitor__deadline_ms: Optional[int] = None
    anomaly__vram_threshold_pct: Optional[float] = None
    anomaly__temp_threshold_c: Optional[float] = None
    ai_diagnostic__enabled: Optional[bool] = None
    ai_diagnostic__api_key_env: Optional[str] = None
    api__host: Optional[str] = None
    api__port: Optional[int] = None
    dashboard__host: Optional[str] = None
    dashboard__port: Optional[int] = None
    logging__level: Optional[str] = None
    ros2__domain_id: Optional[int] = None
    ros2__use_sim_time: Optional[bool] = None


def load_config(config_path: Optional[Path] = None) -> GPUGuardConfig:
    """Load configuration from YAML file and environment variables."""
    config = GPUGuardConfig()

    # Load from YAML file if provided
    if config_path and config_path.exists():
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f)
        if yaml_config:
            config = GPUGuardConfig(**yaml_config)

    # Override with environment variables via Settings
    settings = Settings()
    env_overrides = settings.model_dump(exclude_none=True)

    # Apply environment overrides
    for key, value in env_overrides.items():
        if key == "config_file":
            continue
        # Parse nested keys like collector__poll_interval_ms
        parts = key.split("__")
        if len(parts) == 2:
            section, field = parts
            if hasattr(config, section):
                section_obj = getattr(config, section)
                if hasattr(section_obj, field):
                    # Handle special parsing
                    if field == "gpu_indices" and isinstance(value, str):
                        value = [int(x.strip()) for x in value.split(",")]
                    elif field == "topics" and isinstance(value, str):
                        value = [x.strip() for x in value.split(",")]
                    elif field == "cors_origins" and isinstance(value, str):
                        value = [x.strip() for x in value.split(",")]
                    setattr(section_obj, field, value)

    return config


# Global config instance
_config: Optional[GPUGuardConfig] = None


def get_config(config_path: Optional[Path] = None) -> GPUGuardConfig:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = load_config(config_path)
    return _config


def set_config(config: GPUGuardConfig) -> None:
    """Set global configuration instance."""
    global _config
    _config = config