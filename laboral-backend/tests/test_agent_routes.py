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
