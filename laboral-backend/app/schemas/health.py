from __future__ import annotations

from pydantic import BaseModel


class HealthCheckResult(BaseModel):
    ok: bool
    version: str
    checks: dict[str, dict] = {}
