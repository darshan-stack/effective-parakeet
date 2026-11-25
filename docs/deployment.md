# GPUGuard Deployment Guide

## Prerequisites

### System Requirements
- **OS**: Ubuntu 22.04 LTS or 24.04 LTS (bare metal recommended)
- **GPU**: NVIDIA GPU with driver ≥ 535 (Jetson Orin, RTX 30/40 series, A100, etc.)
- **ROS 2**: Jazzy Jalisco (Humble/Iron with minor adjustments)
- **Python**: 3.10+
- **Memory**: 8 GB+ RAM (16 GB+ recommended for YOLO + Nav2)
- **Disk**: 10 GB free space

### NVIDIA Driver Installation
```bash
# Check current driver
nvidia-smi

# If not installed or old version:
sudo apt update
sudo ubuntu-drivers autoinstall
# OR specific version:
sudo apt install nvidia-driver-535

# Reboot required
sudo reboot
```

Verify:
```bash
nvidia-smi
# Should show driver version ≥ 535
```

### ROS 2 Installation
```bash
# Add ROS 2 repository
sudo apt update && sudo apt install -y curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y ros-jazzy-desktop ros-jazzy-ros2-control ros-jazzy-ros2-controllers

# Add to bashrc
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### Python Environment
```bash
# Create virtual environment
python3 -m venv ~/gpuguard-venv
source ~/gpuguard-venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

## Installation

### From Source (Development)
```bash
cd /home/darshan/GPUGuard
pip install -e .[dev]
```

### Build ROS 2 Package
```bash
mkdir -p ~/ros2_ws/src
ln -sf /home/darshan/GPUGuard/src/gpuguard/ros2 ~/ros2_ws/src/gpuguard_ros2

cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select gpuguard_ros2 --event-handlers console_direct+
source install/setup.bash
```

## Running GPUGuard

### Quick Start (Mock Mode - No GPU Required)
```bash
# Terminal 1: GPU Collector (mock)
gpuguard-collector --mock

# Terminal 2: ROS 2 Monitor
gpuguard-ros-monitor

# Terminal 3: API Server
gpuguard-api

# Terminal 4: Dashboard
gpuguard-dashboard

# Open browser: http://localhost:8050
```

### Production Mode (With GPU)
```bash
# Terminal 1: GPU Collector
gpuguard-collector --poll-interval 100 --gpu-indices 0

# Terminal 2: ROS 2 Monitor
gpuguard-ros-monitor --domain 0

# Terminal 3: API Server
gpuguard-api --host 0.0.0.0 --port 8080

# Terminal 4: Dashboard
gpuguard-dashboard --host 0.0.0.0 --port 8050
```

### ROS 2 Native Launch
```bash
# Source ROS 2 and workspace
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash

# Launch all nodes
ros2 launch gpuguard_ros2 gpuguard.launch.py

# With options:
ros2 launch gpuguard_ros2 gpuguard.launch.py \
  use_mock:=false \
  gpu_indices:="0,1" \
  poll_interval:=100 \
  log_level:=info
```

## Configuration

### Main Config File
`config/gpuguard.yaml` - All settings with environment variable overrides.

### Environment Variables
```bash
# GPU Collector
export GPUGUARD_COLLECTOR__POLL_INTERVAL_MS=100
export GPUGUARD_COLLECTOR__GPU_INDICES="0,1"

# ROS Monitor
export GPUGUARD_MONITOR__TOPICS="/camera/detection,/scan,/odom,/plan"
export GPUGUARD_MONITOR__DEADLINE_MS=50

# Anomaly Detection
export GPUGUARD_ANOMALY__VRAM_THRESHOLD_PCT=85
export GPUGUARD_ANOMALY__TEMP_THRESHOLD_C=80

# AI Diagnostics (requires Anthropic API key)
export GPUGUARD_AI_DIAGNOSTIC__ENABLED=true
export ANTHROPIC_API_KEY="sk-ant-..."

# API Server
export GPUGUARD_API__HOST=0.0.0.0
export GPUGUARD_API__PORT=8080

# Dashboard
export GPUGUARD_DASHBOARD__HOST=0.0.0.0
export GPUGUARD_DASHBOARD__PORT=8050

# ROS 2
export GPUGUARD_ROS2__DOMAIN_ID=0
export GPUGUARD_ROS2__USE_SIM_TIME=false
```

### Custom Config File
```bash
gpuguard-collector --config /path/to/custom.yaml
gpuguard-dashboard --config /path/to/custom.yaml
```

## Docker Deployment (Planned)

```dockerfile
# Dockerfile
FROM nvidia/cuda:12.2-devel-ubuntu22.04

# Install ROS 2, Python deps, GPUGuard
# ...

# Runtime
docker run --gpus all --net=host -it gpuguard:latest
```

## Systemd Services (Production)

### GPU Collector Service
```ini
# /etc/systemd/system/gpuguard-collector.service
[Unit]
Description=GPUGuard GPU Collector
After=network.target

[Service]
Type=simple
User=darshan
WorkingDirectory=/home/darshan/GPUGuard
Environment=PATH=/home/darshan/gpuguard-venv/bin
ExecStart=/home/darshan/gpuguard-venv/bin/gpuguard-collector
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Dashboard Service
```ini
# /etc/systemd/system/gpuguard-dashboard.service
[Unit]
Description=GPUGuard Dashboard
After=network.target gpuguard-api.service

[Service]
Type=simple
User=darshan
WorkingDirectory=/home/darshan/GPUGuard
Environment=PATH=/home/darshan/gpuguard-venv/bin
ExecStart=/home/darshan/gpuguard-venv/bin/gpuguard-dashboard
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gpuguard-collector gpuguard-dashboard
sudo systemctl start gpuguard-collector gpuguard-dashboard
```

## Verification

### Check Collector
```bash
# Should show GPU metrics at 10Hz
gpuguard-collector --mock  # Test without GPU
```

### Check Dashboard
Open `http://localhost:8050` - Should show:
- GPU utilization gauge
- VRAM usage
- Temperature
- Power draw
- ROS topic rates
- Correlation heatmap (after ~30s)

### Check ROS 2 Topics
```bash
ros2 topic list | grep gpuguard
# /gpuguard/gpu_0/state
# /gpuguard/topic_stats
# /gpuguard/correlations
# /gpuguard/anomalies

ros2 topic echo /gpuguard/gpu_0/state --once
```

### Check API
```bash
curl http://localhost:8080/api/v1/health
curl http://localhost:8080/api/v1/status
curl http://localhost:8080/api/v1/gpus
```

## Troubleshooting

### "nvidia-smi not found" / "NVML initialization failed"
- Install NVIDIA driver ≥ 535
- Reboot after driver installation
- Verify with `nvidia-smi`

### "Permission denied" on GPU
```bash
sudo usermod -a -G video $USER
# Log out and back in
```

### ROS 2 topics not showing
- Ensure `ROS_DOMAIN_ID` matches between nodes
- Check firewall: `sudo ufw allow from <subnet> to any port 7400:7500 proto udp`
- Verify DDS: `ros2 doctor`

### Dashboard empty / no data
- Check WebSocket connection in browser DevTools
- Verify API server running on port 8080
- Check CORS origins in config match dashboard URL

### AI Diagnostics not working
- Set `ANTHROPIC_API_KEY` environment variable
- Check `GPUGUARD_AI_DIAGNOSTIC__ENABLED=true`
- Verify API key has credits at console.anthropic.com

### High CPU usage
- Reduce collector poll rate: `poll_interval_ms: 500` (2 Hz)
- Reduce dashboard update interval: `update_interval_ms: 1000`
- Disable unused charts in dashboard config

## Performance Tuning

### For Jetson Orin
```yaml
collector:
  poll_interval_ms: 200  # 5 Hz to reduce CPU
  gpu_indices: [0]

dashboard:
  update_interval_ms: 1000
  max_data_points: 200
```

### For Multi-GPU Systems
```yaml
collector:
  gpu_indices: [0, 1, 2, 3]
  poll_interval_ms: 100
```

### For High-Frequency ROS Topics
```yaml
monitor:
  hz_window_s: 1.0  # Faster rate calculation
  qos_depth: 50     # Larger queue for burst tolerance
```

## Upgrading

```bash
cd /home/darshan/GPUGuard
git pull
pip install -e .[dev] --upgrade

cd ~/ros2_ws
colcon build --packages-select gpuguard_ros2
```

## Uninstalling

```bash
pip uninstall gpuguard
rm -rf ~/gpuguard-venv
# Remove systemd services if installed
```