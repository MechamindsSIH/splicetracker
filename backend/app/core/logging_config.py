"""Structured logging configuration with rotating file handlers."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """Custom formatter that produces structured log lines."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        severity = record.levelname
        module = record.name
        event = getattr(record, "event", record.funcName or "-")
        message = record.getMessage()

        base = f"{timestamp} | {severity:<8} | {module:<30} | {event:<20} | {message}"

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            base = f"{base}\n{record.exc_text}"
        return base


def setup_logging(log_level: str = "INFO", logs_dir: str = "logs") -> None:
    """Configure application-wide logging with console and file handlers.

    Creates rotating file handlers for:
      - application.log  (all messages at configured level)
      - errors.log       (ERROR and above)
      - sensor.log       (sensor-related loggers)
      - alerts.log       (alert-related loggers)
      - simulation.log   (simulation-related loggers)
    """
    log_path = Path(logs_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = StructuredFormatter()

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)
    # Clear existing handlers to avoid duplicates on reload
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Application log (all messages)
    app_handler = RotatingFileHandler(
        str(log_path / "application.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(formatter)
    root.addHandler(app_handler)

    # Error log
    error_handler = RotatingFileHandler(
        str(log_path / "errors.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    # Sensor log
    sensor_logger = logging.getLogger("app.sensors")
    sensor_handler = RotatingFileHandler(
        str(log_path / "sensor.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    sensor_handler.setLevel(level)
    sensor_handler.setFormatter(formatter)
    sensor_logger.addHandler(sensor_handler)

    # Alerts log
    alerts_logger = logging.getLogger("app.alerts")
    alerts_handler = RotatingFileHandler(
        str(log_path / "alerts.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    alerts_handler.setLevel(level)
    alerts_handler.setFormatter(formatter)
    alerts_logger.addHandler(alerts_handler)

    # Simulation log
    sim_logger = logging.getLogger("app.simulation")
    sim_handler = RotatingFileHandler(
        str(log_path / "simulation.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    sim_handler.setLevel(level)
    sim_handler.setFormatter(formatter)
    sim_logger.addHandler(sim_handler)

    # Quieten noisy third-party loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    logging.info("Logging configured: level=%s, dir=%s", log_level, logs_dir)
