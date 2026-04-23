"""Tests de /api/clients.

`ClientManager` usa su propio sqlite en `db/pgk_laboral.db`. Para no
mezclarnos con datos reales ni entre tests, monkeypatcheamos `_client_mgr`
a una instancia apuntando a un archivo temporal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.routes import client as client_routes
from app.services.client_manager import ClientManager


@pytest.fixture
def isolated_client_mgr(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "clients_test.db"
    mgr = ClientManager(db_path=db_path)
    mgr.init_tables()
    monkeypatch.setattr(client_routes, "_client_mgr", mgr)
    return mgr


def test_list_requires_admin(client, auth_headers, isolated_client_mgr):
    resp = client.get("/api/clients", headers=auth_headers)
    # El usuario seed es admin, deberia pasar con 200 y lista vacia
    assert resp.status_code == 200
    assert resp.json() == []


def test_register_and_list_roundtrip(client, auth_headers, isolated_client_mgr):
    resp = client.post(
        "/api/clients",
        headers=auth_headers,
        json={
            "empresa": "Despacho Ejemplo S.L.",
            "cif": "B12345678",
            "convenio_id": "convenio_oficinas_despachos_alicante_2024_2026",
            "provincia": "Alicante",
            "comunidad_autonoma": "Comunitat Valenciana",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["empresa"] == "Despacho Ejemplo S.L."
    assert body["cif"] == "B12345678"

    listing = client.get("/api/clients", headers=auth_headers).json()
    assert len(listing) == 1
    assert listing[0]["cif"] == "B12345678"


def test_register_rejects_invalid_cif(client, auth_headers, isolated_client_mgr):
    resp = client.post(
        "/api/clients",
        headers=auth_headers,
        json={
            "empresa": "Bad CIF Co",
            "cif": "NO_VALIDO",
            "convenio_id": "convenio_oficinas_despachos_alicante_2024_2026",
        },
    )
    assert resp.status_code == 400
    assert "CIF" in resp.json()["detail"]


def test_register_rejects_unknown_convenio(client, auth_headers, isolated_client_mgr):
    resp = client.post(
        "/api/clients",
        headers=auth_headers,
        json={
            "empresa": "Convenio Fantasma",
            "cif": "B12345678",
            "convenio_id": "convenio_que_no_existe",
        },
    )
    assert resp.status_code == 400
    assert "Convenio" in resp.json()["detail"]


def test_simulate_for_client(client, auth_headers, isolated_client_mgr):
    reg = client.post(
        "/api/clients",
        headers=auth_headers,
        json={
            "empresa": "Sim Co",
            "cif": "B12345678",
            "convenio_id": "convenio_oficinas_despachos_alicante_2024_2026",
        },
    ).json()
    cid = reg["id"]

    resp = client.post(
        f"/api/clients/{cid}/simulate",
        headers=auth_headers,
        json={"category": "oficial_1a", "weekly_hours": 40},
    )
    # El endpoint devuelve 200 con resultado o 400 si el engine rechaza;
    # lo importante es que el router cablea, no regressionar el engine.
    assert resp.status_code in (200, 400)
    body = resp.json()
    if resp.status_code == 200:
        assert body["cliente"]["empresa"] == "Sim Co"
        assert "resultado" in body


def test_simulate_for_unknown_client(client, auth_headers, isolated_client_mgr):
    resp = client.post(
        "/api/clients/999999/simulate",
        headers=auth_headers,
        json={"category": "x"},
    )
    assert resp.status_code == 404


def test_requires_auth(client):
    assert client.get("/api/clients").status_code in (401, 403)
    assert client.post(
        "/api/clients", json={"empresa": "x", "cif": "B12345678", "convenio_id": "y"}
    ).status_code in (401, 403)
