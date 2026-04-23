"""Test del endpoint /api/auth/logout."""

from __future__ import annotations


def test_logout_requires_auth(client):
    assert client.post("/api/auth/logout").status_code in (401, 403)


def test_logout_returns_ok(client, auth_headers):
    resp = client.post("/api/auth/logout", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
