# GPUGuard Troubleshooting Guide

## Common Issues

### GPU Collector Issues

#### NVML Initialization Failed
```
Error: Failed to initialize NVML: NVML_ERROR_DRIVER_NOT_LOADED
```
**Causes:**
- NVIDIA driver not installed or version < 535
- Driver not loaded (reboot required after install)
- Running in container without `--gpus all`

**Fix:**
```bash
# Check driver
nvidia-smi

# Install/reinstall driver
sudo apt update && sudo apt install nvidia-driver-535
sudo reboot

# For containers
docker run --gpus all ...
```

#### No GPUs Found
```
Error: No valid GPU indices in [0], available: 0-0
```
**Causes:**
- GPU index out of range
- `GPUGUARD_COLLECTOR__GPU_INDICES` misconfigured

**Fix:**
```bash
# List GPUs
nvidia-smi -L

# Set correct index
export GPUGUARD_COLLECTOR__GPU_INDICES="0"
```

#### Permission Denied
```
Error: NVML_ERROR_INSUFFICIENT_PERMISSIONS
```
**Fix:**
```bash
# Add user to video group
sudo usermod -a -G video $USER
# Log out and back in

# Or run with sudo (not recommended for production)
sudo gpuguard-collector
```

#### Low Collection Rate
```
WARNING: Actual rate 2.3 Hz, target 10 Hz
```
**Causes:**
- System overload
- NVML query taking too long
- Thermal throttling

**Fix:**
```yaml
# Increase poll interval
collector:
  poll_interval_ms: 500  # 2 Hz
```

### ROS 2 Monitor Issues

#### No Topics Discovered
```
WARNING: Could not determine message type for /camera/detection
```
**Causes:**
- Topic not published yet
- Wrong topic name
- Different ROS_DOMAIN_ID

**Fix:**
```bash
# Check topics
ros2 topic list | grep detection

# Check domain
echo $ROS_DOMAIN_ID

# Set domain
export ROS_DOMAIN_ID=0
export GPUGUARD_ROS2__DOMAIN_ID=0
```

#### QoS Mismatch
```
WARNING: QoS mismatch for topic /scan
```
**Fix:**
```yaml
monitor:
  qos_reliability: "best_effort"  # or "reliable"
  qos_durability: "volatile"
  qos_depth: 10
```

#### No Latency Data
- Topic messages must have `std_msgs/Header` with `stamp`
- Check: `ros2 topic echo /camera/detection --once | grep stamp`

### Correlation Engine Issues

#### No Correlations Computed
```
INFO: No correlations computed (insufficient samples)
```
**Causes:**
- `min_samples` not reached (default 50)
- Time sync tolerance too tight
- GPU and ROS streams not overlapping in time

**Fix:**
```yaml
correlation:
  min_samples: 30          # Reduce for testing
  sync_tolerance_ms: 10    # Increase tolerance
  rolling_window: 100      # Smaller window
```

#### All Correlations Near Zero
- Normal if GPU and ROS workloads are independent
- Run GPU stress + YOLO + Nav2 simultaneously to generate correlation

### Anomaly Detection Issues

#### False Positives
- Baseline not established (need ~100 samples)
- Thresholds too sensitive for your hardware

**Fix:**
```yaml
anomaly:
  vram_threshold_pct: 90    # Increase from 85
  temp_threshold_c: 83      # Increase from 80
  isolation_forest_contamination: 0.01  # More conservative
```

#### No Anomalies Detected
- Verify anomalies are being generated
- Check anomaly node subscribed to correct topics

```bash
ros2 topic echo /gpuguard/anomalies
```

### AI Diagnostic Issues

#### "AI diagnostics disabled"
```
WARNING: API key not found in ANTHROPIC_API_KEY, AI diagnostics disabled
```
**Fix:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export GPUGUARD_AI_DIAGNOSTIC__ENABLED=true
```

#### High Latency / Timeout
```
ERROR: AI diagnosis failed: Request timed out
```
**Fix:**
```yaml
ai_diagnostic:
  timeout_s: 60      # Increase from 30
  max_tokens: 1000   # Reduce from 1500
```

### Dashboard Issues

#### Empty Charts / No Data
1. Check WebSocket connection (DevTools → Network → WS)
2. Verify API server: `curl http://localhost:8080/api/v1/status`
3. Check CORS: Dashboard origin must be in `api.cors_origins`

**Fix:**
```yaml
api:
  cors_origins:
    - "http://localhost:8050"
    - "http://127.0.0.1:8050"
    - "http://<your-ip>:8050"
```

#### High Browser CPU
```yaml
dashboard:
  update_interval_ms: 1000  # Reduce from 500
  max_data_points: 200      # Reduce from 500
  charts:
    gpu_clocks: false       # Disable expensive charts
    correlation_heatmap: false
```

### ROS 2 Node Issues

#### Node Fails to Start
```
RuntimeError: Failed to initialize NVML collector
```
**Fix:** Run collector node with `--mock` for testing:
```xml
<arg name="use_mock" default="true"/>
```

#### Messages Not Publishing
- Check topic names: `ros2 topic list | grep gpuguard`
- Verify QoS compatibility between publisher/subscriber
- Check node logs: `ros2 log gpuguard_collector`

### Performance Issues

#### High Memory Usage
- Reduce buffer sizes:
```yaml
collector:
  buffer_size: 5000  # Default 10000
```

#### High CPU Usage
- Reduce poll rates
- Disable unused features:
```yaml
ai_diagnostic:
  enabled: false  # Disable if not needed
correlation:
  granger_maxlag: 5  # Reduce from 10
```

## Debug Mode

### Enable Debug Logging
```bash
export GPUGUARD_LOGGING__LEVEL=DEBUG
export GPUGUARD_LOGGING__FORMAT=text
```

### Component-Level Debug
```bash
# Collector only
GPUGUARD_LOGGING__LEVEL=DEBUG gpuguard-collector --mock

# Dashboard callbacks
# In browser DevTools console:
localStorage.setItem('debug', 'gpuguard:*')
```

### Profile Collection
```python
# Add to collector loop
import cProfile, pstats
profiler = cProfile.Profile()
profiler.enable()
# ... collection loop ...
profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(20)
```

## Log Analysis

### Collector Logs
```bash
# JSON format (default)
tail -f logs/gpuguard.log | jq '.'

# Filter GPU 0
tail -f logs/gpuguard.log | jq 'select(.gpu_id == 0)'

# Filter errors
tail -f logs/gpuguard.log | jq 'select(.level == "ERROR")'
```

### Common Log Patterns
```
# Normal operation
{"level": "INFO", "logger": "gpuguard.collector.nvml", "message": "GPU 0: VRAM=45.2%, GPU=67.1%, Temp=58°C"}

# Throttling detected
{"level": "WARNING", "logger": "gpuguard.anomaly.detector", "message": "ANOMALY [WARNING] GPU 0 clock dropped 25.3% from baseline"}

# Correlation computed
{"level": "DEBUG", "logger": "gpuguard.correlation.correlator", "message": "Correlation utilization_gpu -> /camera/detection: r=0.73, p=0.001"}
```

## Getting Help

### Before Reporting
1. Run with debug logging
2. Collect relevant log snippets
3. Note GPU model, driver version, ROS 2 distro
4. Describe workload (YOLO model, Nav2 config, etc.)

### Useful Commands
```bash
# System info
nvidia-smi
ros2 doctor
pip list | grep -E "gpuguard|nvidia|ros"

# GPUGuard status
curl -s http://localhost:8080/api/v1/status | jq '.'

# Topic health
ros2 topic hz /gpuguard/gpu_0/state
ros2 topic hz /gpuguard/topic_stats
```