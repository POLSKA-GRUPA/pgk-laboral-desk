"""
PGK Laboral Desk — Structured Logging Configuration

JSON-structured logging for production observability.
Inspired by Karpathy's autoresearch patterns for structured, queryable logs.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Include extra fields if present
        for key in (
            "request_id",
            "endpoint",
            "method",
            "status",
            "duration_ms",
            "user_id",
            "client_ip",
            "error_code",
        ):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%H:%M:%S")
        level = record.levelname[0]
        msg = record.getMessage()
        extra_parts = []
        for key in ("endpoint", "method", "status", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                extra_parts.append(f"{key}={val}")
        extras = f" [{' '.join(extra_parts)}]" if extra_parts else ""
        return f"{ts} {level} {record.name}: {msg}{extras}"


def setup_logging(*, json_output: bool | None = None) -> logging.Logger:
    """Configure structured logging for the application.

    Args:
        json_output: Force JSON output. If None, auto-detects from ENVIRONMENT env var.

    Returns:
        The root application logger.
    """
    if json_output is None:
        env = os.environ.get("ENVIRONMENT", "development")
        json_output = env == "production"

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Create application logger
    logger = logging.getLogger("laboral")
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers
    logger.handlers.clear()

    # Configure handler
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    logger.addHandler(handler)

    # Don't propagate to root logger
    logger.propagate = False

    return logger


def get_logger(name: str = "laboral") -> logging.Logger:
    """Get a named logger under the laboral namespace."""
    return logging.getLogger(f"laboral.{name}" if name != "laboral" else name)


class RequestTimer:
    """Context manager for timing request durations."""

    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self) -> RequestTimer:
        self.start_time = time.monotonic()
        return self

    def __exit__(self, *args: object) -> None:
        self.duration_ms = (time.monotonic() - self.start_time) * 1000
