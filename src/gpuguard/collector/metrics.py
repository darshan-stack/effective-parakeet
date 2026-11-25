"""GPU metric definitions and data structures."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
import time


class GPUMetric(str, Enum):
    """Supported GPU metrics."""
    MEMORY_USED = "memory_used"
    MEMORY_TOTAL = "memory_total"
    MEMORY_FREE = "memory_free"
    UTILIZATION_GPU = "utilization_gpu"
    UTILIZATION_MEMORY = "utilization_memory"
    TEMPERATURE_GPU = "temperature_gpu"
    TEMPERATURE_MEMORY = "temperature_memory"
    POWER_DRAW = "power_draw"
    POWER_LIMIT = "power_limit"
    CLOCK_GRAPHICS = "clock_graphics"
    CLOCK_SM = "clock_sm"
    CLOCK_MEM = "clock_mem"
    CLOCK_VIDEO = "clock_video"
    FAN_SPEED = "fan_speed"
    PERFORMANCE_STATE = "performance_state"
    COMPUTE_MODE = "compute_mode"
    ECC_ERRORS_VOLATILE = "ecc_errors_volatile"
    ECC_ERRORS_AGGREGATE = "ecc_errors_aggregate"
    DRIVER_VERSION = "driver_version"
    GPU_NAME = "gpu_name"
    PCIE_THROUGHPUT_TX = "pcie_throughput_tx"
    PCIE_THROUGHPUT_RX = "pcie_throughput_rx"
    PCIE_REPLAY_COUNTER = "pcie_replay_counter"


@dataclass
class GPUSample:
    """Single GPU metric sample."""
    timestamp_ns: int
    gpu_id: int
    metric: GPUMetric
    value: float
    unit: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_ns": self.timestamp_ns,
            "timestamp_s": self.timestamp_ns / 1_000_000_000.0,
            "gpu_id": self.gpu_id,
            "metric": self.metric.value,
            "value": self.value,
            "unit": self.unit,
        }


@dataclass
class GPUState:
    """Complete GPU state snapshot."""
    timestamp_ns: int
    gpu_id: int
    name: str = ""
    driver_version: str = ""

    # Memory (bytes)
    memory_used: int = 0
    memory_total: int = 0
    memory_free: int = 0

    # Utilization (%)
    utilization_gpu: float = 0.0
    utilization_memory: float = 0.0

    # Temperature (Celsius)
    temperature_gpu: float = 0.0
    temperature_memory: float = 0.0

    # Power (watts)
    power_draw: float = 0.0
    power_limit: float = 0.0

    # Clocks (MHz)
    clock_graphics: int = 0
    clock_sm: int = 0
    clock_mem: int = 0
    clock_video: int = 0

    # Fan (%)
    fan_speed: float = 0.0

    # State
    performance_state: int = 0
    compute_mode: int = 0

    # Errors
    ecc_errors_volatile: int = 0
    ecc_errors_aggregate: int = 0

    # PCIe
    pcie_throughput_tx: int = 0
    pcie_throughput_rx: int = 0
    pcie_replay_counter: int = 0

    # Derived
    memory_used_pct: float = 0.0
    power_draw_pct: float = 0.0

    def __post_init__(self):
        if self.memory_total > 0:
            self.memory_used_pct = (self.memory_used / self.memory_total) * 100
        if self.power_limit > 0:
            self.power_draw_pct = (self.power_draw / self.power_limit) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_ns": self.timestamp_ns,
            "timestamp_s": self.timestamp_ns / 1_000_000_000.0,
            "gpu_id": self.gpu_id,
            "name": self.name,
            "driver_version": self.driver_version,
            "memory_used": self.memory_used,
            "memory_total": self.memory_total,
            "memory_free": self.memory_free,
            "memory_used_pct": self.memory_used_pct,
            "utilization_gpu": self.utilization_gpu,
            "utilization_memory": self.utilization_memory,
            "temperature_gpu": self.temperature_gpu,
            "temperature_memory": self.temperature_memory,
            "power_draw": self.power_draw,
            "power_limit": self.power_limit,
            "power_draw_pct": self.power_draw_pct,
            "clock_graphics": self.clock_graphics,
            "clock_sm": self.clock_sm,
            "clock_mem": self.clock_mem,
            "clock_video": self.clock_video,
            "fan_speed": self.fan_speed,
            "performance_state": self.performance_state,
            "compute_mode": self.compute_mode,
            "ecc_errors_volatile": self.ecc_errors_volatile,
            "ecc_errors_aggregate": self.ecc_errors_aggregate,
            "pcie_throughput_tx": self.pcie_throughput_tx,
            "pcie_throughput_rx": self.pcie_throughput_rx,
            "pcie_replay_counter": self.pcie_replay_counter,
        }

    @property
    def is_throttling(self) -> bool:
        """Check if GPU is throttling."""
        return (
            self.temperature_gpu >= 80 or
            self.power_draw_pct >= 90 or
            self.performance_state < 0  # P-state throttling
        )

    @property
    def vram_pressure(self) -> bool:
        """Check if VRAM is under pressure."""
        return self.memory_used_pct >= 85


@dataclass
class GPUInfo:
    """Static GPU information."""
    gpu_id: int
    name: str
    uuid: str
    driver_version: str
    vram_total: int
    compute_capability: str
    pcie_gen: int
    pcie_width: int
    multiprocessors: int
    cuda_cores: int
    tensor_cores: int
    rt_cores: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gpu_id": self.gpu_id,
            "name": self.name,
            "uuid": self.uuid,
            "driver_version": self.driver_version,
            "vram_total": self.vram_total,
            "vram_total_gb": self.vram_total / (1024**3),
            "compute_capability": self.compute_capability,
            "pcie_gen": self.pcie_gen,
            "pcie_width": self.pcie_width,
            "multiprocessors": self.multiprocessors,
            "cuda_cores": self.cuda_cores,
            "tensor_cores": self.tensor_cores,
            "rt_cores": self.rt_cores,
        }


METRIC_UNITS: Dict[GPUMetric, str] = {
    GPUMetric.MEMORY_USED: "bytes",
    GPUMetric.MEMORY_TOTAL: "bytes",
    GPUMetric.MEMORY_FREE: "bytes",
    GPUMetric.UTILIZATION_GPU: "percent",
    GPUMetric.UTILIZATION_MEMORY: "percent",
    GPUMetric.TEMPERATURE_GPU: "celsius",
    GPUMetric.TEMPERATURE_MEMORY: "celsius",
    GPUMetric.POWER_DRAW: "watts",
    GPUMetric.POWER_LIMIT: "watts",
    GPUMetric.CLOCK_GRAPHICS: "mhz",
    GPUMetric.CLOCK_SM: "mhz",
    GPUMetric.CLOCK_MEM: "mhz",
    GPUMetric.CLOCK_VIDEO: "mhz",
    GPUMetric.FAN_SPEED: "percent",
    GPUMetric.PERFORMANCE_STATE: "pstate",
    GPUMetric.COMPUTE_MODE: "mode",
    GPUMetric.ECC_ERRORS_VOLATILE: "count",
    GPUMetric.ECC_ERRORS_AGGREGATE: "count",
    GPUMetric.DRIVER_VERSION: "version",
    GPUMetric.GPU_NAME: "string",
    GPUMetric.PCIE_THROUGHPUT_TX: "kbps",
    GPUMetric.PCIE_THROUGHPUT_RX: "kbps",
    GPUMetric.PCIE_REPLAY_COUNTER: "count",
}

DEFAULT_METRICS = [
    GPUMetric.MEMORY_USED,
    GPUMetric.MEMORY_TOTAL,
    GPUMetric.UTILIZATION_GPU,
    GPUMetric.UTILIZATION_MEMORY,
    GPUMetric.TEMPERATURE_GPU,
    GPUMetric.POWER_DRAW,
    GPUMetric.CLOCK_GRAPHICS,
    GPUMetric.CLOCK_SM,
    GPUMetric.CLOCK_MEM,
    GPUMetric.ECC_ERRORS_VOLATILE,
    GPUMetric.ECC_ERRORS_AGGREGATE,
    GPUMetric.FAN_SPEED,
    GPUMetric.PERFORMANCE_STATE,
    GPUMetric.COMPUTE_MODE,
]