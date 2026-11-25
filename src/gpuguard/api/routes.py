"""FastAPI routes for GPUGuard API."""
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from pydantic import BaseModel
import uuid
import json

from gpuguard.api.websocket_manager import get_websocket_manager
from gpuguard.collector.metrics import GPUState, GPUInfo
from gpuguard.monitor.topic_tracker import TopicStats
from gpuguard.correlation.correlator import CorrelationResult, GrangerResult
from gpuguard.utils.logging import get_logger

logger = get_logger("api.routes")

router = APIRouter()

# Data stores (injected at startup)
_gpu_sampler = None
_ros_monitor = None
_correlator = None


def set_data_stores(gpu_sampler, ros_monitor, correlator):
    """Set data store references."""
    global _gpu_sampler, _ros_monitor, _correlator
    _gpu_sampler = gpu_sampler
    _ros_monitor = ros_monitor
    _correlator = correlator


# Pydantic models for API responses
class GPUStateResponse(BaseModel):
    timestamp_ns: int
    gpu_id: int
    name: str
    memory_used: int
    memory_total: int
    memory_free: int
    memory_used_pct: float
    utilization_gpu: float
    utilization_memory: float
    temperature_gpu: float
    temperature_memory: float
    power_draw: float
    power_limit: float
    power_draw_pct: float
    clock_graphics: int
    clock_sm: int
    clock_mem: int
    clock_video: int
    fan_speed: float
    performance_state: int
    compute_mode: int
    ecc_errors_volatile: int
    ecc_errors_aggregate: int
    is_throttling: bool
    vram_pressure: bool


class TopicStatsResponse(BaseModel):
    topic: str
    message_type: str
    sample_count: int
    current_hz: float
    avg_hz: float
    min_hz: float
    max_hz: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    deadline_ms: float
    deadline_misses: int
    consecutive_misses: int
    avg_size_bytes: float
    max_size_bytes: int


class CorrelationResponse(BaseModel):
    gpu_metric: str
    ros_topic: str
    correlation: float
    p_value: float
    lag_samples: int
    lag_ms: float
    method: str
    sample_count: int
    timestamp_ns: int
    significant: bool


class GrangerResponse(BaseModel):
    gpu_metric: str
    ros_topic: str
    causes_ros: bool
    p_value: float
    f_statistic: float
    optimal_lag: int
    sample_count: int
    timestamp_ns: int


class AnomalyResponse(BaseModel):
    timestamp_ns: int
    type: str
    severity: str
    gpu_metric: Optional[str]
    ros_topic: Optional[str]
    message: str
    value: float
    threshold: float


class SystemStatusResponse(BaseModel):
    status: str
    gpu_count: int
    monitored_topics: int
    active_correlations: int
    active_anomalies: int
    uptime_seconds: float


# REST Endpoints
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gpuguard-api"}


@router.get("/status", response_model=SystemStatusResponse)
async def get_status():
    """Get system status."""
    gpu_count = 0
    monitored_topics = 0
    active_correlations = 0
    active_anomalies = 0

    if _gpu_sampler:
        gpu_count = len(_gpu_sampler.get_all_gpu_ids())
    if _ros_monitor:
        monitored_topics = len(_ros_monitor.get_subscribed_topics())
    if _correlator:
        correlations = _correlator.get_significant_correlations()
        active_correlations = len(correlations)

    return SystemStatusResponse(
        status="running",
        gpu_count=gpu_count,
        monitored_topics=monitored_topics,
        active_correlations=active_correlations,
        active_anomalies=active_anomalies,
        uptime_seconds=0.0,  # TODO: track uptime
    )


@router.get("/gpus", response_model=List[GPUInfo])
async def get_gpu_info():
    """Get static GPU information."""
    if not _gpu_sampler:
        raise HTTPException(status_code=503, detail="GPU sampler not available")

    gpus = []
    for gpu_id in _gpu_sampler.get_all_gpu_ids():
        info = _gpu_sampler.get_gpu_info(gpu_id)
        if info:
            gpus.append(info.to_dict())
    return gpus


@router.get("/gpus/{gpu_id}/state", response_model=GPUStateResponse)
async def get_gpu_state(gpu_id: int):
    """Get current GPU state."""
    if not _gpu_sampler:
        raise HTTPException(status_code=503, detail="GPU sampler not available")

    state = _gpu_sampler.get_latest(gpu_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"GPU {gpu_id} not found")

    return state.to_dict()


@router.get("/gpus/{gpu_id}/history")
async def get_gpu_history(
    gpu_id: int,
    max_samples: int = Query(100, ge=1, le=10000),
):
    """Get GPU state history."""
    if not _gpu_sampler:
        raise HTTPException(status_code=503, detail="GPU sampler not available")

    history = _gpu_sampler.get_history(gpu_id, max_samples)
    return [s.to_dict() for s in history]


@router.get("/gpus/{gpu_id}/stats")
async def get_gpu_window_stats(gpu_id: int):
    """Get GPU window statistics."""
    if not _gpu_sampler:
        raise HTTPException(status_code=503, detail="GPU sampler not available")

    return _gpu_sampler.get_window_stats(gpu_id)


@router.get("/topics", response_model=List[TopicStatsResponse])
async def get_all_topics():
    """Get all topic statistics."""
    if not _ros_monitor:
        raise HTTPException(status_code=503, detail="ROS monitor not available")

    stats = _ros_monitor.get_all_stats()
    return list(stats.values())


@router.get("/topics/{topic_name}", response_model=TopicStatsResponse)
async def get_topic_stats(topic_name: str):
    """Get statistics for a specific topic."""
    if not _ros_monitor:
        raise HTTPException(status_code=503, detail="ROS monitor not available")

    stats = _ros_monitor.get_topic_stats(topic_name)
    if not stats:
        raise HTTPException(status_code=404, detail=f"Topic {topic_name} not found")
    return stats


@router.get("/topics/{topic_name}/deadline")
async def get_topic_deadline(topic_name: str):
    """Get deadline status for a topic."""
    if not _ros_monitor:
        raise HTTPException(status_code=503, detail="ROS monitor not available")

    status = _ros_monitor.get_deadline_status()
    topic_status = status.get(topic_name)
    if not topic_status:
        raise HTTPException(status_code=404, detail=f"Topic {topic_name} not found")
    return topic_status


@router.get("/correlations", response_model=List[CorrelationResponse])
async def get_correlations(
    significant_only: bool = Query(False),
    threshold: float = Query(0.5, ge=0.0, le=1.0),
):
    """Get current correlations."""
    if not _correlator:
        raise HTTPException(status_code=503, detail="Correlator not available")

    if significant_only:
        results = _correlator.get_significant_correlations(threshold)
    else:
        results = _correlator.compute_correlations()

    return [r.to_dict() for r in results]


@router.get("/correlations/matrix")
async def get_correlation_matrix():
    """Get correlation matrix."""
    if not _correlator:
        raise HTTPException(status_code=503, detail="Correlator not available")

    return _correlator.get_correlation_matrix()


@router.get("/granger", response_model=List[GrangerResponse])
async def get_granger_causality():
    """Get Granger causality results."""
    if not _correlator:
        raise HTTPException(status_code=503, detail="Correlator not available")

    results = _correlator.compute_granger_causality()
    return [r.to_dict() for r in results]


@router.get("/chains/{chain_name}/latency")
async def get_chain_latency(chain_name: str):
    """Get latency chain analysis."""
    if not _ros_monitor:
        raise HTTPException(status_code=503, detail="ROS monitor not available")

    result = _ros_monitor.get_chain_latency(chain_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Chain {chain_name} not found")
    return result


@router.get("/anomalies", response_model=List[AnomalyResponse])
async def get_anomalies(
    limit: int = Query(100, ge=1, le=1000),
):
    """Get recent anomalies."""
    # TODO: Integrate with anomaly detector
    return []


# WebSocket endpoint
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data."""
    manager = get_websocket_manager()
    client_id = str(uuid.uuid4())

    await manager.connect(websocket, client_id)

    try:
        # Send initial data
        await _send_initial_data(manager, client_id)

        while True:
            data = await websocket.receive_json()
            await _handle_ws_message(manager, client_id, data)

    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        await manager.disconnect(client_id)


async def _send_initial_data(manager, client_id: str):
    """Send initial data snapshot to new client."""
    # GPU info
    if _gpu_sampler:
        for gpu_id in _gpu_sampler.get_all_gpu_ids():
            state = _gpu_sampler.get_latest(gpu_id)
            if state:
                await manager.send_personal_message(client_id, {
                    "type": "gpu_state",
                    "data": state.to_dict(),
                })
            info = _gpu_sampler.get_gpu_info(gpu_id)
            if info:
                await manager.send_personal_message(client_id, {
                    "type": "gpu_info",
                    "data": info.to_dict(),
                })

    # Topic stats
    if _ros_monitor:
        stats = _ros_monitor.get_all_stats()
        for topic, data in stats.items():
            await manager.send_personal_message(client_id, {
                "type": "topic_stats",
                "data": data,
            })

    # Correlations
    if _correlator:
        correlations = _correlator.compute_correlations()
        for corr in correlations:
            await manager.send_personal_message(client_id, {
                "type": "correlation",
                "data": corr.to_dict(),
            })


async def _handle_ws_message(manager, client_id: str, message: Dict[str, Any]):
    """Handle incoming WebSocket message."""
    msg_type = message.get("type")

    if msg_type == "subscribe":
        topics = message.get("topics", [])
        await manager.subscribe(client_id, topics)

    elif msg_type == "unsubscribe":
        topics = message.get("topics", [])
        await manager.unsubscribe(client_id, topics)

    elif msg_type == "ping":
        await manager.handle_ping(client_id)
        await manager.send_personal_message(client_id, {"type": "pong"})

    elif msg_type == "get_snapshot":
        await _send_initial_data(manager, client_id)

    else:
        logger.warning(f"Unknown WS message type: {msg_type}")


# Callback functions for real-time updates
async def broadcast_gpu_state(state: GPUState):
    """Broadcast GPU state update."""
    manager = get_websocket_manager()
    await manager.queue_broadcast("gpu_state", {
        "type": "gpu_state",
        "data": state.to_dict(),
    })


async def broadcast_topic_stats(topic: str, stats: TopicStats):
    """Broadcast topic statistics update."""
    manager = get_websocket_manager()
    await manager.queue_broadcast("topic_stats", {
        "type": "topic_stats",
        "topic": topic,
        "data": stats.to_dict(),
    })


async def broadcast_correlation(correlation: CorrelationResult):
    """Broadcast correlation update."""
    manager = get_websocket_manager()
    await manager.queue_broadcast("correlation", {
        "type": "correlation",
        "data": correlation.to_dict(),
    })


async def broadcast_anomaly(anomaly: Dict[str, Any]):
    """Broadcast anomaly detection."""
    manager = get_websocket_manager()
    await manager.broadcast_all({
        "type": "anomaly",
        "data": anomaly,
    })