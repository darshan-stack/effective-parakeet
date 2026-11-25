# GPUGuard API Reference

## Base URL
```
http://<host>:8080/api/v1
```

## REST Endpoints

### Health & Status

#### `GET /health`
Health check endpoint.
```json
{
  "status": "healthy",
  "service": "gpuguard-api"
}
```

#### `GET /status`
System status overview.
```json
{
  "status": "running",
  "gpu_count": 1,
  "monitored_topics": 5,
  "active_correlations": 3,
  "active_anomalies": 0,
  "uptime_seconds": 123.45
}
```

### GPU Endpoints

#### `GET /gpus`
List all GPUs with static info.
```json
[
  {
    "gpu_id": 0,
    "name": "NVIDIA GeForce RTX 4090",
    "uuid": "GPU-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "driver_version": "535.154.05",
    "vram_total": 24159191040,
    "vram_total_gb": 22.5,
    "compute_capability": "8.9",
    "pcie_gen": 4,
    "pcie_width": 16,
    "multiprocessors": 128,
    "cuda_cores": 16384,
    "tensor_cores": 512,
    "rt_cores": 128
  }
]
```

#### `GET /gpus/{gpu_id}/state`
Current GPU state snapshot.
```json
{
  "timestamp_ns": 1699999999999999999,
  "gpu_id": 0,
  "name": "NVIDIA GeForce RTX 4090",
  "memory_used": 8589934592,
  "memory_total": 24159191040,
  "memory_free": 15569256448,
  "memory_used_pct": 35.5,
  "utilization_gpu": 67.2,
  "utilization_memory": 42.1,
  "temperature_gpu": 58.0,
  "temperature_memory": 52.0,
  "power_draw": 245.3,
  "power_limit": 450.0,
  "power_draw_pct": 54.5,
  "clock_graphics": 2520,
  "clock_sm": 2520,
  "clock_mem": 10500,
  "clock_video": 1200,
  "fan_speed": 45.0,
  "performance_state": 0,
  "compute_mode": 0,
  "ecc_errors_volatile": 0,
  "ecc_errors_aggregate": 0,
  "is_throttling": false,
  "vram_pressure": false
}
```

#### `GET /gpus/{gpu_id}/history?max_samples=100`
Historical GPU states (ring buffer).
```json
[
  { "timestamp_ns": ..., "gpu_id": 0, "memory_used_pct": 35.5, ... },
  ...
]
```

#### `GET /gpus/{gpu_id}/stats`
Rolling window statistics (default 60s).
```json
{
  "mean": 42.3,
  "std": 12.1,
  "min": 15.0,
  "max": 89.0,
  "rate_hz": 9.98,
  "count": 598,
  "p50": 40.2,
  "p90": 65.1,
  "p95": 72.3,
  "p99": 85.7
}
```

### ROS 2 Topic Endpoints

#### `GET /topics`
All topic statistics.
```json
[
  {
    "topic": "/camera/detection",
    "message_type": "vision_msgs/Detection2DArray",
    "sample_count": 1500,
    "current_hz": 29.8,
    "avg_hz": 30.1,
    "min_hz": 28.5,
    "max_hz": 31.2,
    "avg_latency_ms": 12.4,
    "min_latency_ms": 3.1,
    "max_latency_ms": 45.2,
    "p50_latency_ms": 10.2,
    "p90_latency_ms": 22.8,
    "p95_latency_ms": 31.5,
    "p99_latency_ms": 42.1,
    "deadline_ms": 33.3,
    "deadline_misses": 2,
    "consecutive_misses": 0,
    "avg_size_bytes": 2048,
    "max_size_bytes": 8192
  }
]
```

#### `GET /topics/{topic_name}`
Single topic statistics.

#### `GET /topics/{topic_name}/deadline`
Deadline miss status for a topic.
```json
{
  "misses": 2,
  "consecutive_misses": 0,
  "deadline_ms": 33.3,
  "current_hz": 29.8,
  "expected_hz": 30.0
}
```

### Correlation Endpoints

#### `GET /correlations?significant_only=false&threshold=0.5`
Current correlations.
```json
[
  {
    "gpu_metric": "utilization_gpu",
    "ros_topic": "/camera/detection",
    "correlation": 0.73,
    "p_value": 0.001,
    "lag_samples": 1,
    "lag_ms": 100.0,
    "method": "pearson",
    "sample_count": 150,
    "timestamp_ns": 1699999999999999999,
    "significant": true
  }
]
```

#### `GET /correlations/matrix`
Correlation matrix (GPU metrics × ROS topics).
```json
{
  "utilization_gpu": {
    "/camera/detection": 0.73,
    "/scan": 0.12,
    "/cmd_vel": -0.05
  },
  "memory_used_pct": {
    "/camera/detection": 0.68,
    "/scan": 0.08,
    "/cmd_vel": -0.02
  }
}
```

### Granger Causality

#### `GET /granger`
Granger causality test results.
```json
[
  {
    "gpu_metric": "utilization_gpu",
    "ros_topic": "/camera/detection",
    "causes_ros": true,
    "p_value": 0.003,
    "f_statistic": 12.4,
    "optimal_lag": 1,
    "sample_count": 150,
    "timestamp_ns": 1699999999999999999
  }
]
```

### Latency Chains

#### `GET /chains/{chain_name}/latency`
End-to-end latency for a chain.
```json
{
  "chain": "perception",
  "topics": {
    "/camera/image_raw": { "avg_ms": 5.2, "max_ms": 12.1, "min_ms": 2.0, "count": 150 },
    "/camera/detection": { "avg_ms": 18.4, "max_ms": 45.2, "min_ms": 8.1, "count": 150 },
    "/perception/objects": { "avg_ms": 22.1, "max_ms": 52.3, "min_ms": 10.5, "count": 150 }
  },
  "total_samples": 450
}
```

Available chains: `perception`, `navigation`, `localization`

### Anomalies

#### `GET /anomalies?limit=100`
Recent anomalies.
```json
[
  {
    "timestamp_ns": 1699999999999999999,
    "type": "thermal",
    "severity": "warning",
    "gpu_metric": "temperature_gpu",
    "ros_topic": "",
    "message": "GPU 0 high temperature: 82.5°C",
    "value": 82.5,
    "threshold": 80.0
  }
]
```

## WebSocket API

### Connection
```
ws://<host>:8081/ws
```

### Message Format
All messages are JSON with `type` field.

### Client → Server

#### Subscribe
```json
{
  "type": "subscribe",
  "topics": ["gpu_state", "topic_stats", "correlation", "anomaly"]
}
```

#### Unsubscribe
```json
{
  "type": "unsubscribe",
  "topics": ["gpu_state"]
}
```

#### Ping
```json
{ "type": "ping" }
```

#### Request Snapshot
```json
{ "type": "get_snapshot" }
```

### Server → Client

#### GPU State
```json
{
  "type": "gpu_state",
  "data": { ... GPUState object ... }
}
```

#### Topic Stats
```json
{
  "type": "topic_stats",
  "topic": "/camera/detection",
  "data": { ... TopicStats object ... }
}
```

#### Correlation
```json
{
  "type": "correlation",
  "data": { ... Correlation object ... }
}
```

#### Anomaly
```json
{
  "type": "anomaly",
  "data": { ... Anomaly object ... }
}
```

#### Pong
```json
{ "type": "pong" }
```

#### Error
```json
{
  "type": "error",
  "message": "Invalid topic name"
}
```

## ROS 2 Messages

### GPUState (`gpuguard_ros2/msg/GPUState`)
Published on `/gpuguard/gpu_{id}/state` (Best Effort, 10Hz)

### TopicStats (`gpuguard_ros2/msg/TopicStats`)
Published on `/gpuguard/topic_stats` (Reliable, 1Hz)

### Correlation (`gpuguard_ros2/msg/Correlation`)
Published on `/gpuguard/correlations` (Best Effort, 0.5Hz)

### Anomaly (`gpuguard_ros2/msg/Anomaly`)
Published on `/gpuguard/anomalies` (Reliable, event-driven)

## Error Responses

All endpoints may return:
```json
{
  "detail": "Error description"
}
```

HTTP Status Codes:
- `200` - Success
- `404` - Not found (GPU, topic, chain)
- `503` - Service unavailable (component not initialized)
- `500` - Internal server error

## Rate Limiting

Default: 100 requests/minute per client IP.
Configure via `api.rate_limit` in config.