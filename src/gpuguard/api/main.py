"""FastAPI application for GPUGuard."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from gpuguard.api.routes import router, set_data_stores, broadcast_gpu_state, broadcast_topic_stats
from gpuguard.api.websocket_manager import get_websocket_manager
from gpuguard.utils.config import get_config, APIConfig
from gpuguard.utils.logging import get_logger, init_logging

logger = get_logger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting GPUGuard API...")
    config = get_config()
    init_logging()

    # Data stores will be injected by the main application
    # set_data_stores(gpu_sampler, ros_monitor, correlator)

    yield

    # Shutdown
    logger.info("Shutting down GPUGuard API...")
    ws_manager = get_websocket_manager()
    await ws_manager.close_all()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    config = get_config()
    api_config = config.api

    app = FastAPI(
        title="GPUGuard API",
        description="Real-time GPU observability and ROS 2 correlation API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router, prefix="/api/v1")

    return app


def run_api(
    gpu_sampler=None,
    ros_monitor=None,
    correlator=None,
    host: str = "0.0.0.0",
    port: int = 8080,
):
    """Run the API server."""
    from gpuguard.api.routes import set_data_stores

    # Inject data stores
    set_data_stores(gpu_sampler, ros_monitor, correlator)

    config = get_config()
    api_config = config.api

    # Use provided host/port or config
    host = host or api_config.host
    port = port or api_config.port

    uvicorn.run(
        "gpuguard.api.main:create_app",
        factory=True,
        host=host,
        port=port,
        log_level=config.logging.level.lower(),
        access_log=True,
    )


# For direct module execution
if __name__ == "__main__":
    run_api()