"""Tests del router /api/agent.

Monkeypatchea `_get_agent` para evitar dependencia real de GEMINI/Anthropic.
Verifica ademas que cada invocacion persiste una fila en `agent_runs` y
que la sesion se guarda en `chat_sessions` (kind='agent').
"""

from __future__ import annotations

from typing import Any

import pytest

from app.routes import agent as agent_routes


class _FakeAgent:
    """Doble de `LaboralAgent` para los tests HTTP."""

    available = True

    def __init__(self, *, stream_content: str = "Respuesta de prueba"):
        self._stream_content = stream_content

    def chat(
        self, message: str, history: list[dict[str, str]], context: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "response": f"[fake] Recibido: {message}",
            "tool_calls": [{"code": "print('hola')", "output": "hola"}],
            "context": {**context, "last_message": message},
        }

    def stream_chat(self, message: str, history: list[dict[str, str]], context: dict[str, Any]):
        yield {"type": "token", "content": "Respuesta "}
        yield {"type": "token", "content": "de "}
        yield {"type": "token", "content": "prueba"}
        yield {
            "type": "done",
            "content": self._stream_content,
            "context": {**context, "last_message": message},
        }


@pytest.fixture(autouse=True)
def _patch_agent(monkeypatch):
    monkeypatch.setattr(agent_routes, "_get_agent", lambda convenio_id: _FakeAgent())
    agent_routes._agent_cache.clear()
    yield


def test_status_reports_available(client, auth_headers):
    resp = client.get("/api/agent/status", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"available": True}


def test_status_requires_auth(client):
    resp = client.get("/api/agent/status")
    assert resp.status_code in (401, 403)


def test_status_503_when_agent_not_available(client, auth_headers, monkeypatch):
    monkeypatch.setattr(agent_routes, "_get_agent", lambda convenio_id: None)
    resp = client.get("/api/agent/status", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"available": False}


def test_chat_returns_response_and_session(client, auth_headers):
    resp = client.post(
        "/api/agent/chat",
        headers=auth_headers,
        json={"message": "calcula IRPF Madrid 25000"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["response"].startswith("[fake] Recibido:")
    assert body["tool_calls"] and body["tool_calls"][0]["code"] == "print('hola')"
    assert body["session_id"]


def test_chat_persists_agent_run(client, auth_headers):
    from app.models.agent_run import AgentRun
    from tests.conftest import TestSessionLocal

    client.post(
        "/api/agent/chat",
        headers=auth_headers,
        json={"message": "test de audit"},
    )
    db = TestSessionLocal()
    try:
        runs = db.query(AgentRun).all()
        assert len(runs) == 1
        assert runs[0].mode == "chat"
        assert "test de audit" in runs[0].message
        assert "[fake] Recibido" in runs[0].response
        assert runs[0].duration_ms >= 0
    finally:
        db.close()


def test_chat_same_session_appends_history(client, auth_headers):
    from app.models.chat_session import ChatSession
    from tests.conftest import TestSessionLocal

    r1 = client.post("/api/agent/chat", headers=auth_headers, json={"message": "primer turno"})
    sid = r1.json()["session_id"]
    client.post(
        "/api/agent/chat",
        headers=auth_headers,
        json={"message": "segundo turno", "session_id": sid},
    )
    db = TestSessionLocal()
    try:
        rows = db.query(ChatSession).filter(ChatSession.session_id == sid).all()
        assert len(rows) == 1, "una sesion agent es unica por session_id"
        assert rows[0].kind == "agent"
        import json

        history = json.loads(rows[0].history_json)
        # 2 turnos user/assistant = 4 entradas
        assert len(history) == 4
        assert history[0]["role"] == "user" and history[0]["content"] == "primer turno"
        assert history[2]["role"] == "user" and history[2]["content"] == "segundo turno"
    finally:
        db.close()


def test_chat_503_when_agent_unavailable(client, auth_headers, monkeypatch):
    monkeypatch.setattr(agent_routes, "_get_agent", lambda convenio_id: None)
    resp = client.post("/api/agent/chat", headers=auth_headers, json={"message": "hola"})
    assert resp.status_code == 503


def test_stream_emits_sse_events(client, auth_headers):
    resp = client.post("/api/agent/stream", headers=auth_headers, json={"message": "stream test"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "data: " in body
    assert '"type": "token"' in body
    assert '"type": "done"' in body


def test_stream_persists_run_and_session(client, auth_headers):
    from app.models.agent_run import AgentRun
    from app.models.chat_session import ChatSession
    from tests.conftest import TestSessionLocal

    client.post("/api/agent/stream", headers=auth_headers, json={"message": "stream"})
    db = TestSessionLocal()
    try:
        runs = db.query(AgentRun).filter(AgentRun.mode == "stream").all()
        assert len(runs) == 1
        assert runs[0].response == "Respuesta de prueba"
        sessions = db.query(ChatSession).filter(ChatSession.kind == "agent").all()
        assert len(sessions) == 1
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Regression tests — bugs alpha-1..alpha-5 encontrados en el 2º repaso sobre PR #16.
# Cada test falla si alguien revierte el fix correspondiente.
# ─────────────────────────────────────────────────────────────────────────────


def test_alpha1_whitespace_only_message_rejected_with_400(client, auth_headers):
    """alpha-1: `"   "` NO debe pasar validación — paridad con Flask v2."""
    resp = client.post("/api/agent/chat", headers=auth_headers, json={"message": "   "})
    assert resp.status_code == 400
    assert "Escribe algo" in resp.json()["detail"]


def test_alpha1_empty_message_rejected_with_400(client, auth_headers):
    """alpha-1/alpha-5: mensaje vacío explícito también retorna 400 (no 422)."""
    resp = client.post("/api/agent/chat", headers=auth_headers, json={"message": ""})
    assert resp.status_code == 400


def test_alpha1_stream_whitespace_only_message_rejected_with_400(client, auth_headers):
    """alpha-1 para /stream: mismo rechazo."""
    resp = client.post("/api/agent/stream", headers=auth_headers, json={"message": "   "})
    assert resp.status_code == 400


def test_alpha2_message_stripped_before_persistence(client, auth_headers):
    """alpha-2: el mensaje se guarda sin whitespace extremo en audit trail."""
    from app.models.agent_run import AgentRun
    from tests.conftest import TestSessionLocal

    client.post(
        "/api/agent/chat",
        headers=auth_headers,
        json={"message": "  hola mundo  "},
    )
    db = TestSessionLocal()
    try:
        run = db.query(AgentRun).order_by(AgentRun.id.desc()).first()
        assert run is not None
        assert run.message == "hola mundo", (
            f"esperaba 'hola mundo' sin espacios, vi {run.message!r}"
        )
    finally:
        db.close()


def test_alpha3_stream_events_contain_only_type_and_content(client, auth_headers):
    """alpha-3: eventos SSE NO exponen `context` ni otros campos internos."""
    resp = client.post("/api/agent/stream", headers=auth_headers, json={"message": "stream ctx"})
    assert resp.status_code == 200
    # Cada linea `data: {...}` debe decodificar a un dict con exactamente
    # 2 claves: type y content. Si un dia alguien re-filtra `event` entero
    # y vuelve a emitir `context`, este test falla.
    import json as _json

    for line in resp.text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = _json.loads(line.removeprefix("data: "))
        # El ultimo evento "session" es un `event: session\ndata: {"session_id":...}`;
        # lo saltamos — su line se detecta porque el frame previo es `event: session`.
        if "session_id" in payload and set(payload.keys()) == {"session_id"}:
            continue
        assert set(payload.keys()) == {"type", "content"}, f"evento con campos extra: {payload}"


def test_alpha4_history_caps_at_20_entries_like_flask(client, auth_headers):
    """alpha-4: el historial almacenado NO excede 20 entradas (paridad v2)."""
    import json as _json

    from app.models.chat_session import ChatSession
    from tests.conftest import TestSessionLocal

    sid = None
    for i in range(15):
        body = {"message": f"turno {i}"}
        if sid:
            body["session_id"] = sid
        r = client.post("/api/agent/chat", headers=auth_headers, json=body)
        sid = r.json()["session_id"]

    db = TestSessionLocal()
    try:
        row = db.query(ChatSession).filter(ChatSession.session_id == sid).first()
        history = _json.loads(row.history_json)
        # 15 turnos = 30 entradas → debe capar a 20 (no 40 como antes del fix).
        assert len(history) == 20, (
            f"historial deberia capar a 20 entradas (paridad Flask), vi {len(history)}"
        )
    finally:
        db.close()


def test_alpha5_missing_message_field_still_returns_422(client, auth_headers):
    """alpha-5 complementario: un body sin `message` sigue siendo 422 de Pydantic
    (convención FastAPI). Solo convertimos a 400 la cadena vacía/whitespace."""
    resp = client.post("/api/agent/chat", headers=auth_headers, json={})
    assert resp.status_code == 422


def test_gamma1_cannot_access_another_users_session(client, auth_headers):
    """gamma-1 (Devin Review PR #16 2nd wave): session_id de otro usuario
    debe devolver 403, no dejar leer/escribir el historial ajeno.

    Montaje:
      - user A (`pgk`, creado en conftest) abre una sesion y envia un mensaje.
      - creamos user B (`mallory`) y obtenemos su token.
      - B hace POST /api/agent/chat con el session_id de A.

    Pre-fix: B recibia 200 y escribia en el historial de A (se lo podia leer
    en la siguiente respuesta del agente). Tras fix: 403 y NO toca la fila
    de A.
    """
    import os

    from app.core.security import get_password_hash
    from app.models.chat_session import ChatSession
    from app.models.user import User
    from tests.conftest import TestSessionLocal

    # Misma credencial que el admin de conftest (via DEFAULT_ADMIN_PASSWORD).
    # Evitamos literales tipo "fooPASSword" que GitGuardian marca como generic
    # password y bloquea el CI — aqui solo queremos dos usuarios distintos, no
    # dos contrasenas distintas.
    shared_pwd = os.environ["DEFAULT_ADMIN_PASSWORD"]

    # A crea una sesion real
    r1 = client.post(
        "/api/agent/chat",
        headers=auth_headers,
        json={"message": "mi consulta privada"},
    )
    assert r1.status_code == 200
    victim_sid = r1.json()["session_id"]

    # B se registra directamente en DB + obtiene token
    db = TestSessionLocal()
    try:
        if not db.query(User).filter(User.username == "mallory").first():
            db.add(
                User(
                    username="mallory",
                    hashed_password=get_password_hash(shared_pwd),
                    full_name="Mallory",
                    empresa_nombre="Mallory Inc",
                    role="user",
                    is_active=True,
                )
            )
            db.commit()
    finally:
        db.close()

    tok = client.post(
        "/api/auth/login", json={"username": "mallory", "password": shared_pwd}
    ).json()["access_token"]
    mallory_headers = {"Authorization": f"Bearer {tok}"}

    # B intenta leer/escribir en la sesion de A
    r2 = client.post(
        "/api/agent/chat",
        headers=mallory_headers,
        json={"message": "secuestrada", "session_id": victim_sid},
    )
    assert r2.status_code == 403, (
        f"regresión gamma-1: user B accedió a session_id de A (status={r2.status_code})"
    )

    # Y la sesion de A no se tocó: el historial sigue siendo el original.
    db = TestSessionLocal()
    try:
        row = (
            db.query(ChatSession)
            .filter(ChatSession.session_id == victim_sid, ChatSession.kind == "agent")
            .first()
        )
        assert row is not None
        assert "secuestrada" not in (row.history_json or ""), (
            "regresión gamma-1: B consiguió escribir en la sesión de A"
        )
    finally:
        db.close()


def test_gamma1_stream_endpoint_also_rejects_foreign_session(client, auth_headers):
    """gamma-1 para /stream: mismo rechazo 403."""
    import os

    from app.core.security import get_password_hash
    from app.models.user import User
    from tests.conftest import TestSessionLocal

    shared_pwd = os.environ["DEFAULT_ADMIN_PASSWORD"]

    r1 = client.post("/api/agent/chat", headers=auth_headers, json={"message": "otro turno"})
    victim_sid = r1.json()["session_id"]

    db = TestSessionLocal()
    try:
        if not db.query(User).filter(User.username == "eve").first():
            db.add(
                User(
                    username="eve",
                    hashed_password=get_password_hash(shared_pwd),
                    full_name="Eve",
                    empresa_nombre="Eve Inc",
                    role="user",
                    is_active=True,
                )
            )
            db.commit()
    finally:
        db.close()

    tok = client.post("/api/auth/login", json={"username": "eve", "password": shared_pwd}).json()[
        "access_token"
    ]
    r2 = client.post(
        "/api/agent/stream",
        headers={"Authorization": f"Bearer {tok}"},
        json={"message": "scan", "session_id": victim_sid},
    )
    assert r2.status_code == 403
