# ROS 2 Topic Statistics message
# Published by gpuguard_monitor node

builtin_interfaces/Time stamp
string topic
string message_type
uint64 sample_count

# Rate (Hz)
float64 current_hz
float64 avg_hz
float64 min_hz
float64 max_hz

# Latency (ms)
float64 avg_latency_ms
float64 min_latency_ms
float64 max_latency_ms
float64 p50_latency_ms
float64 p90_latency_ms
float64 p95_latency_ms
float64 p99_latency_ms

# Deadline tracking
float64 deadline_ms
int32 deadline_misses
int32 consecutive_misses

# Message size (bytes)
float64 avg_size_bytes
int64 max_size_bytes