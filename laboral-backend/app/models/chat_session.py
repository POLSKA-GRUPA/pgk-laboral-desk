"""Sesiones persistentes para `/api/chat` y `/api/agent/*`.

Reemplaza el dict en memoria `_chat_sessions` de `routes/chat.py` para que
(a) la sesion sobreviva reinicios del proceso y (b) funcione con
`uvicorn --workers N` (cada worker tenia antes su propio dict y las
conversaciones se cortaban al rebalancear).

Una sesion se identifica por `session_id` (UUID cliente) + `kind`
(`"chat"` o `"agent"`). Los dos campos JSON serializan historial y
contexto (variables persistentes entre turnos del sandbox CodeAct).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (UniqueConstraint("session_id", "kind", name="uq_chat_sessions_sid_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="chat")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    history_json: Mapped[str] = mapped_column(Text, default="[]")
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )
