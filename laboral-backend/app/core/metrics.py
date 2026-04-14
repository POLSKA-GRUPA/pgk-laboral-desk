"""Simple metrics collection for service monitoring."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ServiceMetrics:
    _lock: Lock = field(default_factory=Lock)
    _call_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _error_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _total_duration: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _durations: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def record(self, service: str, duration_s: float, error: bool = False):
        with self._lock:
            self._call_counts[service] += 1
            self._total_duration[service] += duration_s
            if error:
                self._error_counts[service] += 1
            self._durations[service].append(duration_s)
            if len(self._durations[service]) > 1000:
                self._durations[service] = self._durations[service][-1000:]

    def get_stats(self) -> dict:
        with self._lock:
            result = {}
            for service in self._call_counts:
                durations = sorted(self._durations.get(service, []))
                p50 = durations[len(durations) // 2] if durations else 0
                p95 = durations[int(len(durations) * 0.95)] if durations else 0
                calls = self._call_counts[service]
                result[service] = {
                    "calls": calls,
                    "errors": self._error_counts.get(service, 0),
                    "avg_duration_ms": round((self._total_duration[service] / calls) * 1000, 2)
                    if calls
                    else 0,
                    "p50_ms": round(p50 * 1000, 2),
                    "p95_ms": round(p95 * 1000, 2),
                }
            return result


metrics = ServiceMetrics()
