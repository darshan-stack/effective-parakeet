# GPUGuard Architecture

## System Overview

GPUGuard is a layered observability system connecting NVIDIA GPU driver telemetry to ROS 2 runtime performance.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GPUGuard Architecture                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────────────┐  │
│  │  NVIDIA  │    │  GPU     │    │  Time       │    │  Correlation     │  │
│  │  GPU     │───▶│ Collector│───▶│ Synchronizer│───▶│ Engine           │  │
│  │ (NVML)   │    │ (10-100Hz)│   │ (sub-5ms)   │    │ (Pearson/Granger)│  │
│  └──────────┘    └──────────┘    └─────────────┘    └────────┬─────────┘  │
│                                                                │           │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐              │           │
│  │  ROS 2   │    │  ROS 2   │    │  Anomaly    │◀─────────────┘           │
│  │  Topics  │───▶│ Monitor  │───▶│ Detector    │                           │
│  │          │    │ (rate,   │    │ (thresholds │                           │
│  └──────────┘    │ latency) │    │  + ML)      │                           │
│                  └──────────┘    └──────┬──────┘                           │
│                                         │                                  │
│                                         ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    AI Diagnostic Engine (Claude API)                 │  │
│  │  Input: Anomalies + GPU State + Topic Stats + Correlations          │  │
│  │  Output: Root Cause + Explanation + Actionable Recommendations      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                         │                                  │
│                  ┌──────────────────────┼──────────────────────┐          │
│                  ▼                      ▼                      ▼          │
│         ┌──────────────┐        ┌──────────────┐        ┌──────────────┐  │
│         │ FastAPI +    │        │   Plotly     │        │  ROS 2       │  │
│         │ WebSocket    │◀──────▶│   Dash       │        │  Nodes       │  │
│         │ Backend      │        │   Dashboard  │        │  (Pub/Sub)   │  │
│         └──────────────┘        └──────────────┘        └──────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Layer Details

### 1. Hardware/OS Layer
- **Ubuntu 22.04/24.04** bare metal or VM with GPU passthrough
- **NVIDIA Driver ≥ 535** (NVML API requirement)
- **ROS 2 Jazzy** (Humble/Iron compatible)

### 2. GPU Telemetry Collector (`gpuguard.collector`)
- **NVMLCollector**: Python bindings to `nvidia-ml-py` (NVML)
- **Metrics polled**: VRAM, compute %, temperature, clocks, power, fan, ECC, PCIe, P-state
- **Rate**: 10–100 Hz configurable (default 100ms = 10 Hz)
- **MockNVMLCollector**: Identical interface for CI/development without GPU
- **Ring buffer**: In-memory history (default 10k samples per GPU)
- **Callbacks**: Async notification to sampler, correlator, anomaly detector

### 3. ROS 2 Monitor (`gpuguard.monitor`)
- **ROSMonitorNode**: rclpy node subscribing to configured topics
- **TopicTracker**: Computes rate (Hz), latency (header stamp → receipt), deadline misses
- **LatencyAnalyzer**: Chain analysis (sensor → perception → planning → control)
- **QoS**: Configurable reliability/durability/depth
- **Output**: TopicStats messages + callback notifications

### 4. Time Synchronization (`gpuguard.correlation.time_sync`)
- **TimeSynchronizer**: NTP-style 4-timestamp alignment between GPU and ROS clocks
- **Tolerance**: Default 5ms (configurable)
- **StreamAligner**: Multi-stream alignment to common time base
- **ClockSync**: Drift estimation for long-running sessions

### 5. Correlation Engine (`gpuguard.correlation.correlator`)
- **Correlator**: Rolling-window Pearson/Spearman/Kendall correlation with lag search
- **Granger Causality**: statsmodels-based test (GPU → ROS predictive relationship)
- **Min samples**: 50 (configurable)
- **Max lag**: 10 samples (configurable)
- **Significance**: p < 0.05 (configurable)

### 6. Anomaly Detection (`gpuguard.anomaly.detector`)
- **Statistical thresholds**: VRAM >85%, temp >80°C, clock drop >15%, etc.
- **Isolation Forest**: ML-based multivariate anomaly detection (sklearn)
- **Training**: Online, retrains every 500 samples
- **Output**: Anomaly objects with type, severity, message, value, threshold

### 7. AI Diagnostic Engine (`gpuguard.diagnostic.ai_diagnostic`)
- **AIDiagnosticEngine**: Anthropic Claude API integration
- **Prompt engineering**: Structured system prompt + formatted context
- **Caching**: TTL-based (default 5 min) to reduce API calls
- **Output**: Diagnosis with root_cause, explanation, recommendations, confidence

### 8. Recommendation Engine (`gpuguard.diagnostic.recommendation_engine`)
- **Rule-based**: Maps anomaly types to actionable recommendations
- **Categories**: Model optimization, resource management, hardware config, software config, system tuning
- **Cross-correlation**: Detects compound patterns (thermal + latency = GPU→ROS impact)

### 9. Backend API (`gpuguard.api`)
- **FastAPI**: REST endpoints for current state, history, correlations, anomalies
- **WebSocket**: Real-time streaming to dashboard
- **Topics**: gpu_state, topic_stats, correlation, anomaly, chain_latency
- **CORS**: Configurable origins

### 10. Dashboard (`gpuguard.dashboard`)
- **Plotly Dash**: Reactive web UI with Bootstrap/CYBORG theme
- **Components**: Gauge charts, time series, heatmaps, anomaly timelines, tables
- **Real-time**: WebSocket updates (fallback: 500ms polling interval)
- **Sections**: GPU Overview, ROS Topics, Correlations, Anomalies, Latency Chains

### 11. ROS 2 Integration (`gpuguard_ros2`)
- **Custom Messages**: GPUState, TopicStats, Correlation, Anomaly
- **Nodes**:
  - `gpuguard_collector`: Publishes GPUState
  - `gpuguard_monitor`: Publishes TopicStats
  - `gpuguard_correlator`: Publishes Correlation
  - `gpuguard_anomaly`: Publishes Anomaly
- **Launch**: `gpuguard.launch.py` with configurable parameters

## Data Flow

```
GPU (NVML)                    ROS 2 Topics
    │                             │
    ▼                             ▼
Collector                   Monitor Node
    │                             │
    ├── GPUState ────────────────▶│ (via callback)
    │                             │
    ▼                             ▼
Sampler ◀────────────────────── TopicTracker
    │                             │
    ├── Latest/History ─────────▶│ (via callback)
    │                             │
    ▼                             ▼
Correlator ◀──────────────────────────────▶ (via add_gpu_metric/add_ros_metric)
    │
    ├── Correlations ──────────────────────▶ Anomaly Detector
    │                                         │
    ▼                                         ▼
AI Diagnostic Engine ◀───────────────────── Anomalies
    │
    ├── Diagnosis ─────────────────────────▶ Recommendation Engine
    │
    ▼
FastAPI + WebSocket ◀─────────────────────▶ Dashboard
    │
    ├── REST ─────────────────────────────▶ External consumers
    │
    ▼
ROS 2 Nodes (gpuguard_ros2) ◀─────────────▶ ROS 2 Ecosystem
```

## Configuration

All layers configured via `config/gpuguard.yaml` with environment variable overrides (`GPUGUARD_*`).

Key sections:
- `collector`: poll_interval_ms, gpu_indices, metrics, buffer_size
- `monitor`: topics, deadline_ms, window_size, hz_window_s
- `correlation`: sync_tolerance_ms, min_samples, granger_maxlag, rolling_window
- `anomaly`: thresholds for VRAM, temp, clock, power, latency, Hz, deadlines
- `ai_diagnostic`: enabled, model, max_tokens, temperature, cache_ttl_s
- `api`: host, port, ws_port, cors_origins
- `dashboard`: host, port, update_interval_ms, max_data_points, theme

## Deployment Modes

1. **Standalone Python**: `gpuguard-collector`, `gpuguard-dashboard`, `gpuguard-api`
2. **ROS 2 Native**: `ros2 launch gpuguard_ros2 gpuguard.launch.py`
3. **Mock Mode**: `--mock` flag for collector (no GPU needed)
4. **Docker**: Multi-stage build with CUDA base image (planned)

## Security

- No authentication in MVP (local/trusted network only)
- WebSocket origin validation via CORS
- API rate limiting (configurable)
- No sensitive data in logs (metrics only)
- Claude API key via environment variable only