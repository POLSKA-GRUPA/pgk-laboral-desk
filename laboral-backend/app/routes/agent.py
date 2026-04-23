"""Rutas del agente CodeAct.

Porta a FastAPI los endpoints Flask `/api/agent/{status,chat,stream}`
usando el servicio `app.services.laboral_agent.LaboralAgent` (ya existente).

Diferencias frente a la version Flask:
- La persistencia de historial/contexto pasa de `session["agent_history"]`
  (cookie Flask) a la tabla `chat_sessions` (kind="agent"). Esto hace que
  la sesion sobreviva reinicios y funcione con `uvicorn --workers N`.
- Cada invocacion genera una fila en `agent_runs` (audit trail H14) con
  mensaje, respuesta, tool_calls y duracion.
- Auth por JWT (`Depends(get_current_user)`), no cookie Flask.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.agent_run import AgentRun
from app.models.chat_session import ChatSession
from app.models.user import User
from app.schemas.agent import AgentChatRequest, AgentChatResponse, AgentStatusResponse
from app.services.engine import LaboralEngine
from app.services.laboral_agent import LaboralAgent

router = APIRouter(prefix="/agent", tags=["agent"])

# Paridad con Flask v2 (`app.py:488 -> history[-20:]`): se guardan las ultimas
# 20 entradas, es decir 10 turnos user/assistant. Si lo subes aqui, cambia la
# experiencia conversacional del agente respecto a la version legacy.
_HISTORY_MAX_ENTRIES = 20
_DEFAULT_CONVENIO = "convenio_acuaticas_2025_2027"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"

# Cache de agentes por convenio. `LaboralAgent.__init__` instancia el cliente
# LLM y compila el system prompt; reutilizar la instancia ahorra 1-3 s por
# llamada sin cambiar semantica (el estado conversacional vive en DB).
_agent_cache: dict[str, LaboralAgent] = {}


def _load_convenio_safe(convenio_id: str) -> dict[str, Any]:
    safe_name = Path(convenio_id).name
    path = _DATA_DIR / f"{safe_name}.json"
    if not path.resolve().is_relative_to(_DATA_DIR.resolve()):
        raise FileNotFoundError("Convenio ID invalido")
    if not path.exists():
        raise FileNotFoundError(f"Convenio no encontrado: {convenio_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _get_agent(convenio_id: str) -> LaboralAgent | None:
    """Devuelve la instancia cacheada, o None si no hay LLM configurado."""
    if convenio_id in _agent_cache:
        return _agent_cache[convenio_id]
    try:
        convenio_data = _load_convenio_safe(convenio_id)
    except FileNotFoundError:
        return None
    engine = LaboralEngine(convenio_data)
    agent = LaboralAgent(engine)
    if not agent.available:
        return None
    _agent_cache[convenio_id] = agent
    return agent


def _resolve_convenio(requested: str | None, user: User) -> str:
    return requested or user.convenio_id or _DEFAULT_CONVENIO


def _load_session(
    db: Session, session_id: str, user_id: int
) -> tuple[ChatSession, list[dict[str, str]], dict[str, Any]]:
    row = (
        db.query(ChatSession)
        .filter(ChatSession.session_id == session_id, ChatSession.kind == "agent")
        .first()
    )
    if row is None:
        row = ChatSession(session_id=session_id, kind="agent", user_id=user_id)
        db.add(row)
        db.flush()
    history = json.loads(row.history_json or "[]")
    context = json.loads(row.context_json or "{}")
    return row, history, context


def _save_session(
    db: Session,
    row: ChatSession,
    history: list[dict[str, str]],
    context: dict[str, Any],
) -> None:
    if len(history) > _HISTORY_MAX_ENTRIES:
        history = history[-_HISTORY_MAX_ENTRIES:]
    row.history_json = json.dumps(history, ensure_ascii=False)
    row.context_json = json.dumps(context, ensure_ascii=False, default=str)


def _record_run(
    db: Session,
    *,
    user_id: int,
    session_id: str,
    convenio_id: str,
    mode: str,
    message: str,
    response: str,
    tool_calls: list[dict[str, Any]],
    error: str | None,
    duration_ms: int,
) -> None:
    db.add(
        AgentRun(
            user_id=user_id,
            session_id=session_id,
            convenio_id=convenio_id,
            mode=mode,
            message=message[:5000],
            response=response[:20000],
            tool_calls_json=json.dumps(tool_calls, ensure_ascii=False, default=str)[:50000],
            error=error,
            duration_ms=duration_ms,
        )
    )


@router.get("/status", response_model=AgentStatusResponse)
def agent_status(
    convenio_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    convenio = _resolve_convenio(convenio_id, current_user)
    return AgentStatusResponse(available=_get_agent(convenio) is not None)


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(
    data: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not data.message:
        # Paridad con Flask v2 (`app.py:465`): `400 {"error": "Escribe algo"}`.
        # Pydantic acepta la cadena ya stripada (vacio si todo era whitespace);
        # aqui la convertimos a HTTPException(400) en vez de dejar el 422.
        raise HTTPException(status_code=400, detail="Escribe algo")
    convenio = _resolve_convenio(data.convenio_id, current_user)
    agent = _get_agent(convenio)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agente IA no disponible. Configura GOOGLE_API_KEY o ANTHROPIC_API_KEY.",
        )

    session_id = data.session_id or str(uuid.uuid4())
    row, history, context = _load_session(db, session_id, current_user.id)

    start = time.monotonic()
    error: str | None = None
    try:
        result = agent.chat(data.message, history=history, context=context)
    except Exception as exc:  # pragma: no cover — defensivo, el sandbox tiene su propio try
        error = repr(exc)
        raise HTTPException(status_code=500, detail=f"Error del agente: {exc}") from exc
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        if error is not None:
            _record_run(
                db,
                user_id=current_user.id,
                session_id=session_id,
                convenio_id=convenio,
                mode="chat",
                message=data.message,
                response="",
                tool_calls=[],
                error=error,
                duration_ms=duration_ms,
            )
            db.commit()

    response_text = str(result.get("response", ""))
    tool_calls = list(result.get("tool_calls", []))
    new_history = list(history)
    new_history.append({"role": "user", "content": data.message})
    new_history.append({"role": "assistant", "content": response_text})
    _save_session(db, row, new_history, dict(result.get("context", context)))
    _record_run(
        db,
        user_id=current_user.id,
        session_id=session_id,
        convenio_id=convenio,
        mode="chat",
        message=data.message,
        response=response_text,
        tool_calls=tool_calls,
        error=None,
        duration_ms=duration_ms,
    )
    db.commit()

    return AgentChatResponse(response=response_text, tool_calls=tool_calls, session_id=session_id)


@router.post("/stream")
def agent_stream(
    data: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Server-Sent Events con la respuesta del agente.

    El formato de cada evento es `data: {"type": "token|code|result|done", "content": "..."}\\n\\n`.
    Persistimos historial/runs tras agotar el generador del agente, por el
    mismo motivo que la version Flask: solo sabemos el texto final al
    consumir el ultimo evento (`done`).
    """
    if not data.message:
        raise HTTPException(status_code=400, detail="Escribe algo")
    convenio = _resolve_convenio(data.convenio_id, current_user)
    agent = _get_agent(convenio)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agente IA no disponible. Configura GOOGLE_API_KEY o ANTHROPIC_API_KEY.",
        )

    session_id = data.session_id or str(uuid.uuid4())
    row, history, context = _load_session(db, session_id, current_user.id)

    # Materializamos todos los eventos antes de streamear — igual que hacia
    # la version Flask — para poder persistir historial y agent_run en DB
    # con la respuesta completa. Los mensajes laborales tipicos tardan
    # 1-5 s, es aceptable para no perder el audit trail.
    events: list[dict[str, Any]] = []
    full_response = ""
    final_ctx = dict(context)
    start = time.monotonic()
    error: str | None = None
    try:
        for event in agent.stream_chat(data.message, history=history, context=context):
            etype = str(event.get("type", "token"))
            content = str(event.get("content", ""))
            # Paridad con Flask v2 (`app.py:527-530`): solo exponemos
            # `type`+`content` al cliente. `context` y otros campos internos
            # quedan en el servidor para no inflar el payload SSE.
            events.append({"type": etype, "content": content})
            if etype == "token":
                full_response += content
            elif etype == "done":
                if content:
                    full_response = content
                final_ctx = dict(event.get("context", final_ctx))
    except Exception as exc:
        error = repr(exc)
        events.append({"type": "done", "content": f"Error del agente: {exc}"})
    duration_ms = int((time.monotonic() - start) * 1000)

    new_history = list(history)
    new_history.append({"role": "user", "content": data.message})
    new_history.append({"role": "assistant", "content": full_response})
    _save_session(db, row, new_history, final_ctx)
    _record_run(
        db,
        user_id=current_user.id,
        session_id=session_id,
        convenio_id=convenio,
        mode="stream",
        message=data.message,
        response=full_response,
        tool_calls=[],
        error=error,
        duration_ms=duration_ms,
    )
    db.commit()

    def generate() -> Iterator[str]:
        for evt in events:
            yield f"data: {json.dumps(evt, ensure_ascii=False, default=str)}\n\n"
        yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
