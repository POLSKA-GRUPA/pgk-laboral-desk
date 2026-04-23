from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    session_id: str | None = None
    convenio_id: str | None = None


class AgentChatResponse(BaseModel):
    response: str
    tool_calls: list[dict[str, Any]] = []
    session_id: str


class AgentStatusResponse(BaseModel):
    available: bool
