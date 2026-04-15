from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    convenio_id: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    parsed: dict[str, Any] | None = None
    simulation: dict[str, Any] | None = None
    traces: list[str] = []
    session_id: str | None = None
    options: list[dict[str, Any]] | None = None
