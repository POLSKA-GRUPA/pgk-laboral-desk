from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentChatRequest(BaseModel):
    message: str = Field(max_length=5000)
    session_id: str | None = None
    convenio_id: str | None = None

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str) -> str:
        """Paridad con Flask v2 (`app.py:463`): `str(data.get("message", "")).strip()`.

        El rechazo de cadenas vacias NO se hace aqui con ValueError (que
        Pydantic convierte en 422) sino en el route handler con
        HTTPException(400), igual que hacia Flask. Asi cualquier cliente que
        chequee `status === 400` sigue funcionando sin cambios.
        """
        return v.strip()


class AgentChatResponse(BaseModel):
    response: str
    tool_calls: list[dict[str, Any]] = []
    session_id: str


class AgentStatusResponse(BaseModel):
    available: bool
