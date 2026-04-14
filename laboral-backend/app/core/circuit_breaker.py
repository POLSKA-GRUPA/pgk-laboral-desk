"""Circuit Breaker pattern for external service protection."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from enum import Enum
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


_SERVICE_CONFIGS: dict[str, dict[str, Any]] = {
    "perplexity": {"failure_threshold": 3, "recovery_timeout": 60},
    "gemini": {"failure_threshold": 5, "recovery_timeout": 30},
    "anthropic": {"failure_threshold": 5, "recovery_timeout": 30},
    "zai": {"failure_threshold": 5, "recovery_timeout": 30},
    "boe_api": {"failure_threshold": 3, "recovery_timeout": 120},
}


class CircuitBreaker:
    def __init__(self, service_name: str, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0
        self._call_counts: dict[str, int] = defaultdict(int)

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit %s: OPEN -> HALF_OPEN", self.service_name)
                return True
            return False
        return True

    def record_success(self):
        self._call_counts["success"] += 1
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info("Circuit %s: HALF_OPEN -> CLOSED", self.service_name)

    def record_failure(self):
        self._call_counts["failure"] += 1
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "Circuit %s: -> OPEN (failures: %d)", self.service_name, self.failure_count
            )

    @property
    def stats(self) -> dict:
        return {
            "state": self.state.value,
            "failures": self.failure_count,
            "calls": dict(self._call_counts),
        }


_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(service: str) -> CircuitBreaker:
    if service not in _breakers:
        cfg = _SERVICE_CONFIGS.get(service, {})
        _breakers[service] = CircuitBreaker(
            service_name=service,
            failure_threshold=cfg.get("failure_threshold", 3),
            recovery_timeout=cfg.get("recovery_timeout", 60),
        )
    return _breakers[service]


def circuit_breaker(service: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            breaker = get_breaker(service)
            if not breaker.can_execute():
                raise Exception(f"Circuit breaker OPEN for {service}")
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as exc:
                breaker.record_failure()
                raise

        return wrapper

    return decorator


def all_breaker_stats() -> dict[str, dict]:
    return {name: b.stats for name, b in _breakers.items()}
