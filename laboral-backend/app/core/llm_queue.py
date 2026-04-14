"""LLM request queue — prevents API flooding."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock, Semaphore


class LLMQueue:
    def __init__(self, max_concurrent: int = 5):
        self._max = max_concurrent
        self._semaphores: dict[str, Semaphore] = {}
        self._lock = Lock()
        self._active: dict[str, int] = defaultdict(int)

    def _get_semaphore(self, service: str) -> Semaphore:
        with self._lock:
            if service not in self._semaphores:
                self._semaphores[service] = Semaphore(self._max)
            return self._semaphores[service]

    def acquire(self, service: str) -> bool:
        sem = self._get_semaphore(service)
        acquired = sem.acquire(blocking=False)
        if acquired:
            self._active[service] += 1
        return acquired

    def release(self, service: str):
        sem = self._get_semaphore(service)
        sem.release()
        self._active[service] = max(0, self._active[service] - 1)

    @property
    def stats(self) -> dict:
        return {
            "max_concurrent": self._max,
            "active": dict(self._active),
        }


llm_queue = LLMQueue()
