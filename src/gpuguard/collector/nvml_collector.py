"""NVML-based GPU telemetry collector."""
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

import pynvml
from pynvml import NVMLError

from gpuguard.collector.metrics import (
    GPUMetric,
    GPUState,
    GPUInfo,
    GPUState,
    DEFAULT_METRICS,
    METRIC_UNITS,
)
from gpuguard.utils.time_utils import now_ns, RateLimiter
from gpuguard.utils.logging import get_logger
from gpuguard.utils.config import get_config, CollectorConfig


logger = get_logger("collector.nvml")


@dataclass
class CollectorStats:
    """Collector statistics."""
    samples_collected: int = 0
    samples_failed: int = 0
    last_sample_time_ns: int = 0
    last_error: Optional[str] = None
    gpu_count: int = 0


class NVMLCollector:
    """Collects GPU telemetry using NVIDIA NVML API."""

    def __init__(self, config: Optional[CollectorConfig] = None):
        self.config = config or get_config().collector
        self._initialized = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[GPUState], None]] = []
        self._lock = threading.RLock()
        self._stats = CollectorStats()
        self._gpu_infos: Dict[int, GPUInfo] = {}
        self._rate_limiter: Optional[RateLimiter] = None

    def initialize(self) -> bool:
        """Initialize NVML and discover GPUs."""
        try:
            pynvml.nvmlInit()
            self._initialized = True

            gpu_count = pynvml.nvmlDeviceGetCount()
            self._stats.gpu_count = gpu_count

            # Validate GPU indices
            valid_indices = [i for i in self.config.gpu_indices if 0 <= i < gpu_count]
            if not valid_indices:
                logger.error(f"No valid GPU indices in {self.config.gpu_indices}, available: 0-{gpu_count-1}")
                return False
            self.config.gpu_indices = valid_indices

            # Cache GPU info
            for gpu_id in self.config.gpu_indices:
                handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
                self._gpu_infos[gpu_id] = self._get_gpu_info(handle, gpu_id)

            # Setup rate limiter
            hz = 1000 / self.config.poll_interval_ms
            self._rate_limiter = RateLimiter(hz)

            logger.info(f"NVML initialized: {gpu_count} GPU(s), monitoring {self.config.gpu_indices}")
            return True

        except NVMLError as e:
            logger.error(f"Failed to initialize NVML: {e}")
            return False

    def _get_gpu_info(self, handle, gpu_id: int) -> GPUInfo:
        """Get static GPU information."""
        name = pynvml.nvmlDeviceGetName(handle).decode()
        uuid = pynvml.nvmlDeviceGetUUID(handle).decode()
        driver_version = pynvml.nvmlSystemGetDriverVersion().decode()

        memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_total = memory_info.total

        # Compute capability
        major = pynvml.nvmlDeviceGetCudaComputeCapability(handle)[0]
        minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)[1]
        compute_capability = f"{major}.{minor}"

        # PCIe info
        pcie_gen = 0
        pcie_width = 0
        try:
            pcie_gen = pynvml.nvmlDeviceGetMaxPcieLinkGeneration(handle)
            pcie_width = pynvml.nvmlDeviceGetMaxPcieLinkWidth(handle)
        except NVMLError:
            pass

        # Architecture details (approximate based on name)
        multiprocessors = 0
        cuda_cores = 0
        tensor_cores = 0
        rt_cores = 0
        try:
            multiprocessors = pynvml.nvmlDeviceGetNumMultiprocessors(handle)
            # Estimate cores based on architecture
            if major >= 8:  # Ampere+
                cuda_cores = multiprocessors * 128
                tensor_cores = multiprocessors * 4
                rt_cores = multiprocessors
            elif major >= 7:  # Turing
                cuda_cores = multiprocessors * 64
                tensor_cores = multiprocessors * 8
                rt_cores = multiprocessors
            else:  # Pascal/Volta
                cuda_cores = multiprocessors * 128 if major >= 6 else multiprocessors * 64
        except NVMLError:
            pass

        return GPUInfo(
            gpu_id=gpu_id,
            name=name,
            uuid=uuid,
            driver_version=driver_version,
            vram_total=vram_total,
            compute_capability=compute_capability,
            pcie_gen=pcie_gen,
            pcie_width=pcie_width,
            multiprocessors=multiprocessors,
            cuda_cores=cuda_cores,
            tensor_cores=tensor_cores,
            rt_cores=rt_cores,
        )

    def register_callback(self, callback: Callable[[GPUState], None]) -> None:
        """Register a callback for GPU state updates."""
        with self._lock:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[GPUState], None]) -> None:
        """Unregister a callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def start(self) -> bool:
        """Start the collection thread."""
        if not self._initialized:
            if not self.initialize():
                return False

        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
        logger.info("GPU collector started")
        return True

    def stop(self) -> None:
        """Stop the collection thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("GPU collector stopped")

    def _collect_loop(self) -> None:
        """Main collection loop."""
        while self._running:
            try:
                self._collect_once()
                if self._rate_limiter:
                    self._rate_limiter.sleep()
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                self._stats.samples_failed += 1
                self._stats.last_error = str(e)
                time.sleep(1.0)  # Back off on error

    def _collect_once(self) -> None:
        """Collect one sample from all GPUs."""
        timestamp = now_ns()

        for gpu_id in self.config.gpu_indices:
            try:
                state = self._collect_gpu_state(gpu_id, timestamp)
                self._stats.samples_collected += 1
                self._stats.last_sample_time_ns = timestamp

                # Notify callbacks
                with self._lock:
                    for callback in self._callbacks:
                        try:
                            callback(state)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

            except NVMLError as e:
                logger.error(f"NVML error for GPU {gpu_id}: {e}")
                self._stats.samples_failed += 1
                self._stats.last_error = str(e)
            except Exception as e:
                logger.error(f"Unexpected error collecting GPU {gpu_id}: {e}")
                self._stats.samples_failed += 1
                self._stats.last_error = str(e)

    def _collect_gpu_state(self, gpu_id: int, timestamp: int) -> GPUState:
        """Collect complete state for one GPU."""
        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)

        # Memory
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        memory_used = mem_info.used
        memory_total = mem_info.total
        memory_free = mem_info.free

        # Utilization
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        utilization_gpu = util.gpu
        utilization_memory = util.memory

        # Temperature
        try:
            temp_gpu = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except NVMLError:
            temp_gpu = 0.0

        try:
            temp_mem = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_MEMORY)
        except NVMLError:
            temp_mem = 0.0

        # Power
        try:
            power_draw = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW to W
        except NVMLError:
            power_draw = 0.0

        try:
            power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0
        except NVMLError:
            power_limit = 0.0

        # Clocks
        try:
            clock_graphics = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
        except NVMLError:
            clock_graphics = 0

        try:
            clock_sm = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
        except NVMLError:
            clock_sm = 0

        try:
            clock_mem = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
        except NVMLError:
            clock_mem = 0

        try:
            clock_video = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_VIDEO)
        except NVMLError:
            clock_video = 0

        # Fan
        try:
            fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
        except NVMLError:
            fan_speed = 0.0

        # Performance state
        try:
            pstate = pynvml.nvmlDeviceGetPerformanceState(handle)
        except NVMLError:
            pstate = 0

        # Compute mode
        try:
            compute_mode = pynvml.nvmlDeviceGetComputeMode(handle)
        except NVMLError:
            compute_mode = 0

        # ECC errors
        try:
            ecc_volatile = pynvml.nvmlDeviceGetTotalEccErrors(handle, pynvml.NVML_VOLATILE_ECC)
        except NVMLError:
            ecc_volatile = 0

        try:
            ecc_aggregate = pynvml.nvmlDeviceGetTotalEccErrors(handle, pynvml.NVML_AGGREGATE_ECC)
        except NVMLError:
            ecc_aggregate = 0

        # PCIe
        try:
            pcie_tx = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_TX_BYTES)
        except NVMLError:
            pcie_tx = 0

        try:
            pcie_rx = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_RX_BYTES)
        except NVMLError:
            pcie_rx = 0

        try:
            pcie_replay = pynvml.nvmlDeviceGetPcieReplayCounter(handle)
        except NVMLError:
            pcie_replay = 0

        # GPU info
        gpu_info = self._gpu_infos.get(gpu_id)
        name = gpu_info.name if gpu_info else ""
        driver_version = gpu_info.driver_version if gpu_info else ""

        return GPUState(
            timestamp_ns=timestamp,
            gpu_id=gpu_id,
            name=name,
            driver_version=driver_version,
            memory_used=memory_used,
            memory_total=memory_total,
            memory_free=memory_free,
            utilization_gpu=utilization_gpu,
            utilization_memory=utilization_memory,
            temperature_gpu=temp_gpu,
            temperature_memory=temp_mem,
            power_draw=power_draw,
            power_limit=power_limit,
            clock_graphics=clock_graphics,
            clock_sm=clock_sm,
            clock_mem=clock_mem,
            clock_video=clock_video,
            fan_speed=fan_speed,
            performance_state=pstate,
            compute_mode=compute_mode,
            ecc_errors_volatile=ecc_volatile,
            ecc_errors_aggregate=ecc_aggregate,
            pcie_throughput_tx=pcie_tx,
            pcie_throughput_rx=pcie_rx,
            pcie_replay_counter=pcie_replay,
        )

    def get_gpu_info(self, gpu_id: int) -> Optional[GPUInfo]:
        """Get static GPU info."""
        return self._gpu_infos.get(gpu_id)

    def get_all_gpu_infos(self) -> Dict[int, GPUInfo]:
        """Get all GPU infos."""
        return dict(self._gpu_infos)

    def get_stats(self) -> CollectorStats:
        """Get collector statistics."""
        return self._stats

    def sample_now(self) -> Dict[int, GPUState]:
        """Collect one sample immediately (blocking)."""
        timestamp = now_ns()
        results = {}
        for gpu_id in self.config.gpu_indices:
            try:
                results[gpu_id] = self._collect_gpu_state(gpu_id, timestamp)
            except Exception as e:
                logger.error(f"Failed to sample GPU {gpu_id}: {e}")
        return results

    def shutdown(self) -> None:
        """Clean shutdown."""
        self.stop()
        if self._initialized:
            try:
                pynvml.nvmlShutdown()
            except NVMLError:
                pass
            self._initialized = False


class MockNVMLCollector:
    """Mock collector for testing without GPU."""

    def __init__(self, config: Optional[CollectorConfig] = None):
        self.config = config or get_config().collector
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[GPUState], None]] = []
        self._lock = threading.RLock()
        self._stats = CollectorStats()
        self._gpu_infos: Dict[int, GPUInfo] = {}
        self._base_values = {
            "memory_used": 2_000_000_000,
            "memory_total": 8_000_000_000,
            "utilization_gpu": 30.0,
            "utilization_memory": 25.0,
            "temperature_gpu": 45.0,
            "power_draw": 120.0,
            "power_limit": 250.0,
            "clock_graphics": 1500,
            "clock_sm": 1500,
            "clock_mem": 5000,
            "fan_speed": 40.0,
        }

    def initialize(self) -> bool:
        self._initialized = True
        self._stats.gpu_count = len(self.config.gpu_indices)
        for gpu_id in self.config.gpu_indices:
            self._gpu_infos[gpu_id] = GPUInfo(
                gpu_id=gpu_id,
                name="Mock GPU (RTX 4090)",
                uuid="GPU-mock-uuid",
                driver_version="535.154.05",
                vram_total=8_000_000_000,
                compute_capability="8.9",
                pcie_gen=4,
                pcie_width=16,
                multiprocessors=128,
                cuda_cores=16384,
                tensor_cores=512,
                rt_cores=128,
            )
        self._rate_limiter = RateLimiter(1000 / self.config.poll_interval_ms)
        return True

    def register_callback(self, callback: Callable[[GPUState], None]) -> None:
        with self._lock:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[GPUState], None]) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def start(self) -> bool:
        if self._running:
            return True
        self._running = True
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _collect_loop(self) -> None:
        import random
        while self._running:
            timestamp = now_ns()
            for gpu_id in self.config.gpu_indices:
                # Simulate some variation
                state = GPUState(
                    timestamp_ns=timestamp,
                    gpu_id=gpu_id,
                    name="Mock GPU (RTX 4090)",
                    driver_version="535.154.05",
                    memory_used=self._base_values["memory_used"] + random.randint(-100_000_000, 100_000_000),
                    memory_total=self._base_values["memory_total"],
                    memory_free=self._base_values["memory_total"] - self._base_values["memory_used"],
                    utilization_gpu=max(0, min(100, self._base_values["utilization_gpu"] + random.uniform(-5, 5))),
                    utilization_memory=max(0, min(100, self._base_values["utilization_memory"] + random.uniform(-3, 3))),
                    temperature_gpu=max(30, min(90, self._base_values["temperature_gpu"] + random.uniform(-2, 2))),
                    power_draw=max(50, min(300, self._base_values["power_draw"] + random.uniform(-10, 10))),
                    power_limit=self._base_values["power_limit"],
                    clock_graphics=self._base_values["clock_graphics"],
                    clock_sm=self._base_values["clock_sm"],
                    clock_mem=self._base_values["clock_mem"],
                    fan_speed=self._base_values["fan_speed"],
                    performance_state=0,
                    compute_mode=0,
                    ecc_errors_volatile=0,
                    ecc_errors_aggregate=0,
                )
                with self._lock:
                    for callback in self._callbacks:
                        try:
                            callback(state)
                        except Exception:
                            pass
            if self._rate_limiter:
                self._rate_limiter.sleep()

    def get_gpu_info(self, gpu_id: int) -> Optional[GPUInfo]:
        return self._gpu_infos.get(gpu_id)

    def get_all_gpu_infos(self) -> Dict[int, GPUInfo]:
        return dict(self._gpu_infos)

    def get_stats(self) -> CollectorStats:
        return self._stats

    def sample_now(self) -> Dict[int, GPUState]:
        return {}

    def shutdown(self) -> None:
        self.stop()