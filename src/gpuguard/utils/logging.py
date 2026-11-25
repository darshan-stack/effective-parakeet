"""Logging configuration for GPUGuard."""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

from gpuguard.utils.config import get_config, LoggingConfig


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, "gpu_id"):
            log_obj["gpu_id"] = record.gpu_id
        if hasattr(record, "topic"):
            log_obj["topic"] = record.topic
        if hasattr(record, "metric"):
            log_obj["metric"] = record.metric
        if hasattr(record, "value"):
            log_obj["value"] = record.value

        # Add exception info
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(config: Optional[LoggingConfig] = None) -> logging.Logger:
    """Setup GPUGuard logging."""
    if config is None:
        config = get_config().logging

    # Create logger
    logger = logging.getLogger("gpuguard")
    logger.setLevel(getattr(logging, config.level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatters
    if config.format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation
    log_file = Path(config.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=config.max_size_mb * 1024 * 1024,
        backupCount=config.backup_count,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger."""
    return logging.getLogger(f"gpuguard.{name}")


# Context managers for structured logging
class LogContext:
    """Context manager for adding structured fields to logs."""

    def __init__(self, logger: logging.Logger, **kwargs):
        self.logger = logger
        self.kwargs = kwargs
        self.old_factory = logging.getLogRecordFactory()

    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.kwargs.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)


# Initialize default logger
_default_logger: Optional[logging.Logger] = None


def init_logging(config_path: Optional[Path] = None) -> logging.Logger:
    """Initialize logging system."""
    global _default_logger
    if _default_logger is None:
        from gpuguard.utils.config import load_config
        cfg = load_config(config_path)
        _default_logger = setup_logging(cfg.logging)
    return _default_logger