# GPU State message for ROS 2
# Published by gpuguard_collector node

builtin_interfaces/Time stamp
int32 gpu_id
string name
string driver_version

# Memory (bytes)
uint64 memory_used
uint64 memory_total
uint64 memory_free
float64 memory_used_pct

# Utilization (%)
float64 utilization_gpu
float64 utilization_memory

# Temperature (Celsius)
float64 temperature_gpu
float64 temperature_memory

# Power (watts)
float64 power_draw
float64 power_limit
float64 power_draw_pct

# Clocks (MHz)
int32 clock_graphics
int32 clock_sm
int32 clock_mem
int32 clock_video

# Fan (%)
float64 fan_speed

# State
int32 performance_state
int32 compute_mode

# Errors
int32 ecc_errors_volatile
int32 ecc_errors_aggregate

# PCIe
uint64 pcie_throughput_tx
uint64 pcie_throughput_rx
uint64 pcie_replay_counter

# Flags
bool is_throttling
bool vram_pressure