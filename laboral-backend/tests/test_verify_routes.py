"""Tests de /api/verify-rates y /api/verify-convenio."""

from __future__ import annotations

from typing import Any

from app.routes import verify as verify_routes


class _FakeResult:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def to_dict(self) -> dict[str, Any]:
        return self._payload


class _FakeRatesVerifier:
    def __init__(self, *, available: bool, payload: dict[str, Any] | None = None):
        self.available = available
        self._payload = payload or {"ok": True}

    def verify_all(self, force: bool = False) -> _FakeResult:
        return _FakeResult(self._payload)


class _FakeConvenioVerifier:
    def __init__(self, *, available: bool, payload: dict[str, Any] | None = None):
        self.available = available
        self._payload = payload or {"ok": True}
        self.calls: list[dict[str, Any]] = []

    def verify(self, **kwargs: Any) -> _FakeResult:
        self.calls.append(kwargs)
        return _FakeResult(self._payload)


def test_verify_rates_503_when_unavailable(client, auth_headers, monkeypatch):
    monkeypatch.setattr(verify_routes, "_rates_verifier", _FakeRatesVerifier(available=False))
    resp = client.get("/api/verify-rates", headers=auth_headers)
    assert resp.status_code == 503


def test_verify_rates_passes_through_payload(client, auth_headers, monkeypatch):
    fake = _FakeRatesVerifier(
        available=True, payload={"ok": True, "ss_rates": {"general": "30.57%"}}
    )
    monkeypatch.setattr(verify_routes, "_rates_verifier", fake)
    resp = client.get("/api/verify-rates", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["details"]["ss_rates"]["general"] == "30.57%"


def test_verify_convenio_503_when_unavailable(client, auth_headers, monkeypatch):
    monkeypatch.setattr(verify_routes, "_convenio_verifier", _FakeConvenioVerifier(available=False))
    resp = client.post(
        "/api/verify-convenio",
        headers=auth_headers,
        json={"sector": "oficinas despachos"},
    )
    assert resp.status_code == 503


def test_verify_convenio_passes_through(client, auth_headers, monkeypatch):
    fake = _FakeConvenioVerifier(
        available=True, payload={"ok": True, "resumen": "Convenio vigente"}
    )
    monkeypatch.setattr(verify_routes, "_convenio_verifier", fake)

    resp = client.post(
        "/api/verify-convenio",
        headers=auth_headers,
        json={
            "sector": "oficinas despachos",
            "provincia": "Alicante",
            "codigo_convenio": "03000635011994",
            "vigencia_hasta": 2026,
        },
    )
    assert resp.status_code == 200, resp.text
    assert fake.calls == [
        {
            "sector": "oficinas despachos",
            "provincia": "Alicante",
            "codigo_convenio": "03000635011994",
            "vigencia_hasta": 2026,
        }
    ]


def test_verify_requires_auth(client):
    assert client.get("/api/verify-rates").status_code in (401, 403)
    assert client.post("/api/verify-convenio", json={"sector": "x"}).status_code in (401, 403)
