# GPUGuard — AI-Powered GPU Observability for ROS 2 Robotics

[![ROS 2](https://img.shields.io/badge/ROS%202-Jazzy-blue.svg)](https://docs.ros.org/en/jazzy/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![NVIDIA](https://img.shields.io/badge/NVIDIA-NVML-76B900.svg)](https://developer.nvidia.com/nvidia-management-library-nvml)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **GPUGuard** monitors GPU health (VRAM, compute, thermal, driver errors) at the driver level using NVIDIA NVML and correlates it in real-time with ROS 2 topic latencies. When GPU bottlenecks cause navigation deadline misses, GPUGuard tells you exactly why — and what to change.

## The Problem

Every physical AI robot today runs neural net inference (YOLO, segmentation, pose estimation) on a GPU **simultaneously** with navigation stacks (Nav2, SLAM, localization) on the CPU. When the GPU hits VRAM limits, thermal throttles, or driver errors:

- Inference latency spikes (18ms → 71ms+)
- ROS 2 perception topics fall behind
- Navigation costmap updates miss cycles
- Robot misses obstacle avoidance deadlines
- **No existing tool connects GPU health to robot behavior**

## The Solution

GPUGuard is the **correlation layer** between GPU driver telemetry and ROS 2 runtime performance:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   NVIDIA GPU    │     │   GPUGuard      │     │   ROS 2 Stack   │
│   (NVML API)    │────▶│  Collector +    │────▶│  (Nav2, YOLO,   │
│   VRAM, Temp,   │     │  Correlation    │     │   SLAM, etc.)   │
│   Clocks, Errs  │     │  Engine + AI    │     │  Topic Latency  │
└─────────────────┘     │  Diagnostics    │     └─────────────────┘
                        └─────────────────┘
```

**Key Capabilities:**
- 🔍 **Driver-level GPU telemetry** via NVML (VRAM, compute %, temperature, clock speeds, ECC errors, power)
- 🔗 **Real-time correlation** between GPU metrics and ROS 2 topic latency
- 🤖 **AI diagnostic engine** (Claude API) explaining root causes in plain English
- 📊 **Live dashboard** (Plotly/Dash) showing GPU health ↔ ROS 2 performance
- ⚡ **Anomaly detection** (statistical + ML) for thermal throttling, VRAM pressure, driver faults
- 🎯 **Actionable recommendations** (batch size, cooling, kernel params, model optimization)

## Quick Start

```bash
# 1. Install dependencies (Ubuntu 22.04/24.04 + NVIDIA GPU)
./scripts/install_dependencies.sh

# 2. Build and install
cd /home/darshan/GPUGuard
pip install -e .

# 3. Run GPUGuard collector (terminal 1)
gpuguard-collector --ros-domain 0

# 4. Run ROS 2 monitoring agent (terminal 2)
gpuguard-ros-monitor

# 5. Launch dashboard (terminal 3)
gpuguard-dashboard
```

## Demo Scenario

```bash
# Terminal 1: Start GPU stress + YOLO inference
python3 scripts/demo_yolo_inference.py --model yolov8n --device cuda --batch 4

# Terminal 2: Run Nav2 navigation stack
ros2 launch nav2_bringup navigation_launch.py

# Terminal 3: GPUGuard monitors correlation live
gpuguard-dashboard
```

**Watch GPUGuard detect:**
- VRAM climbing to 89% → detection latency 18ms → 71ms
- GPU temp 78°C → clock drop 340MHz (thermal throttling)
- Nav2 costmap updates falling 2 cycles behind
- **AI diagnosis:** "Reduce YOLO batch size from 4 to 1 or add active cooling"

## Architecture Overview

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Hardware/OS** | Ubuntu 22.04+, NVIDIA Driver 535+ | GPU access, NVML availability |
| **GPU Telemetry** | Python `nvidia-ml-py` (NVML bindings) | Poll VRAM, compute, temp, clocks, errors at 10-100Hz |
| **ROS 2 Monitor** | `rclpy`, `ros2topic` API | Track topic Hz, latency, deadline misses |
| **Correlation Engine** | Pandas, NumPy, SciPy | Time-sync, cross-correlation, Granger causality |
| **Anomaly Detection** | Isolation Forest, statistical thresholds | Detect throttling, VRAM pressure, driver faults |
| **AI Diagnostics** | Anthropic Claude API | Plain-English root cause + fix recommendations |
| **Backend API** | FastAPI + WebSockets | Real-time data to dashboard |
| **Frontend** | Plotly Dash + WebSocket | Live GPU/ROS 2 correlated visualization |

## Project Structure

```
GPUGuard/
├── src/gpuguard/
│   ├── collector/          # NVML GPU telemetry collector
│   │   ├── nvml_collector.py
│   │   ├── metrics.py
│   │   └── sampler.py
│   ├── monitor/            # ROS 2 topic monitoring
│   │   ├── ros_monitor.py
│   │   ├── topic_tracker.py
│   │   └── latency_analyzer.py
│   ├── correlation/        # GPU ↔ ROS 2 correlation engine
│   │   ├── time_sync.py
│   │   ├── correlator.py
│   │   └── anomaly_detector.py
│   ├── diagnostic/         # AI diagnostic engine
│   │   ├── ai_diagnostic.py
│   │   ├── prompt_templates.py
│   │   └── recommendation_engine.py
│   ├── api/                # FastAPI backend + WebSockets
│   │   ├── main.py
│   │   ├── routes.py
│   │   └── websocket_manager.py
│   ├── dashboard/          # Plotly Dash frontend
│   │   ├── app.py
│   │   ├── layouts.py
│   │   ├── callbacks.py
│   │   └── components/
│   ├── ros2/               # ROS 2 integration nodes
│   │   ├── gpuguard_node.py
│   │   └── msg/
│   └── utils/              # Shared utilities
│       ├── config.py
│       ├── logging.py
│       └── time_utils.py
├── config/
│   ├── gpuguard.yaml       # Main configuration
│   ├── thresholds.yaml     # Anomaly thresholds
│   └── dashboard.yaml      # Dashboard settings
├── launch/
│   └── gpuguard.launch.py  # ROS 2 launch file
├── scripts/
│   ├── install_dependencies.sh
│   ├── demo_yolo_inference.py
│   ├── demo_gpu_stress.py
│   └── benchmark.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── deployment.md
│   └── troubleshooting.md
├── pyproject.toml
├── requirements.txt
└── LICENSE
```

## Configuration

```yaml
# config/gpuguard.yaml
collector:
  poll_interval_ms: 100          # 10Hz default
  gpu_indices: [0]               # Monitor GPU 0
  metrics:
    - memory_used
    - memory_total
    - utilization_gpu
    - utilization_memory
    - temperature_gpu
    - power_draw
    - clock_graphics
    - clock_sm
    - ecc_errors

monitor:
  topics:
    - /camera/detection          # YOLO output
    - /scan                      # LiDAR
    - /odom                      # Odometry
    - /plan                      # Nav2 path
  deadline_ms: 50                # Expected topic period
  window_size: 100               # Samples for statistics

correlation:
  sync_tolerance_ms: 5           # Max time offset for correlation
  min_samples: 50                # Minimum samples for correlation
  granger_maxlag: 10             # Max lag for Granger causality

anomaly:
  vram_threshold_pct: 85         # VRAM pressure threshold
  temp_threshold_c: 80           # Thermal throttling threshold
  clock_drop_threshold_pct: 15   # Clock drop detection
  latency_spike_threshold: 3.0   # Std deviations for spike

ai_diagnostic:
  enabled: true
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 1000
  temperature: 0.1
```

## Requirements

- **OS:** Ubuntu 22.04 or 24.04 (bare metal or VM with GPU passthrough)
- **GPU:** NVIDIA GPU with driver ≥ 535 (Jetson Orin, RTX 30/40 series, A100, etc.)
- **ROS 2:** Jazzy (or Humble/Iron with minor adjustments)
- **Python:** 3.10+
- **Claude API key** (for AI diagnostics) - optional, works without

## License

MIT License - see [LICENSE](LICENSE) for details.

## Citation

If you use GPUGuard in research, please cite:

```bibtex
@software{gpuguard2026,
  title = {GPUGuard: AI-Powered GPU Observability for ROS 2 Robotics},
  author = {Darshan},
  year = {2026},
  url = {https://github.com/darshan-stack/GPUGuard}
}
```

---

**Built for the physical AI robotics community.** Every robot running inference on a GPU needs this observability layer.