"""Audit trail del agente CodeAct.

Cada invocacion de `LaboralAgent.chat()` o `.stream_chat()` persiste una fila
aqui con el mensaje del usuario, el codigo Python que el LLM genero, la salida
del sandbox y cualquier traceback. Esto cierra el hueco H14 del audit: en
dominio fiscal es imprescindible poder reconstruir *como* calculo el agente
una respuesta.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    convenio_id: Mapped[str] = mapped_column(String(200), default="")
    mode: Mapped[str] = mapped_column(String(20), default="chat")  # "chat" | "stream"
    message: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    # JSON serializado con la lista de tool_calls (cada uno {"code": "..."})
    tool_calls_json: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
