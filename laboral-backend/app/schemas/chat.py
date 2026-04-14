from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    convenio_id: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    parsed: Optional[dict[str, Any]] = None
    simulation: Optional[dict[str, Any]] = None
    traces: list[str] = []
    session_id: Optional[str] = None
    options: Optional[list[dict[str, Any]]] = None
