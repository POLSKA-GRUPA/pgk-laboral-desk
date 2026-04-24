"""Tests del endpoint de alta masiva de empleados desde CSV."""

from __future__ import annotations

import io

from app.routes.employees_bulk import TEMPLATE_COLUMNS


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    buf.write(",".join(TEMPLATE_COLUMNS) + "\n")
    for row in rows:
        buf.write(",".join(row.get(col, "") for col in TEMPLATE_COLUMNS) + "\n")
    return buf.getvalue().encode("utf-8")


def _valid_row(**overrides):
    base = {
        "nombre": "Juan Pérez",
        "nif": "12345678Z",
        "naf": f"2812345678{2812345678 % 97:02d}",
        "categoria": "Peón agrícola",
        "contrato_tipo": "fijo-discontinuo",
        "codigo_contrato_sepe": "300",
        "jornada_horas": "40",
        "fecha_inicio": "2026-05-01",
        "fecha_fin": "",
        "salario_bruto_mensual": "1200",
        "num_hijos": "0",
        "region": "generica",
        "domicilio": "",
        "email": "",
        "telefono": "",
        "sexo": "1",
        "fecha_nacimiento": "1990-03-15",
        "nacionalidad": "724",
        "municipio_residencia": "28079",
        "pais_residencia": "724",
        "temporada": "Temporada-2026-V",
        "notas": "",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return base


def test_template_download(client, auth_headers):
    resp = client.get("/api/employees/bulk-import/template", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    # Cabecera con todas las columnas.
    first_line = body.split("\n", 1)[0]
    for col in TEMPLATE_COLUMNS:
        assert col in first_line


def test_template_sample_row_passes_validation(client, auth_headers):
    """La fila de ejemplo de la plantilla debe pasar dry-run sin errores
    para que el operador pueda usarla como base directa."""
    tmpl = client.get("/api/employees/bulk-import/template", headers=auth_headers).text
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("plantilla.csv", tmpl.encode("utf-8"), "text/csv")},
    )
    body = resp.json()
    assert body["invalid_rows"] == 0, body["errors"]
    assert body["valid_rows"] == 1


def test_jornada_cero_es_error(client, auth_headers):
    """jornada_horas=0 debe ser error, no reemplazo silencioso por 40."""
    data = _csv_bytes([_valid_row(jornada_horas="0")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    body = resp.json()
    assert any(e["field"] == "jornada_horas" for e in body["errors"])


def test_template_requires_auth(client):
    resp = client.get("/api/employees/bulk-import/template")
    assert resp.status_code == 401


def test_bulk_import_dry_run_happy_path(client, auth_headers):
    data = _csv_bytes([_valid_row(), _valid_row(nombre="Ana López", nif="87654321X")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("plantilla.csv", data, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 2
    assert body["invalid_rows"] == 0
    assert body["dry_run"] is True
    assert body["created"] == 0
    assert body["errors"] == []


def test_bulk_import_detecta_nif_invalido(client, auth_headers):
    data = _csv_bytes([_valid_row(nif="12345678A")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["invalid_rows"] == 1
    assert any(e["field"] == "nif" for e in body["errors"])


def test_bulk_import_detecta_naf_invalido(client, auth_headers):
    data = _csv_bytes([_valid_row(naf="281234567899")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    body = resp.json()
    assert any(e["field"] == "naf" for e in body["errors"])


def test_bulk_import_detecta_nif_duplicado(client, auth_headers):
    data = _csv_bytes([_valid_row(), _valid_row(nombre="Otro")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    body = resp.json()
    assert any(e["field"] == "nif" and "duplicado" in e["message"] for e in body["errors"])


def test_bulk_import_detecta_fecha_invalida(client, auth_headers):
    data = _csv_bytes([_valid_row(fecha_inicio="01/05/2026")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    body = resp.json()
    assert any(e["field"] == "fecha_inicio" for e in body["errors"])


def test_bulk_import_detecta_obligatorios_vacios(client, auth_headers):
    data = _csv_bytes([_valid_row(nombre="", categoria="", fecha_inicio="")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    body = resp.json()
    campos = {e["field"] for e in body["errors"]}
    assert "nombre" in campos
    assert "categoria" in campos
    assert "fecha_inicio" in campos


def test_bulk_import_real_crea_filas(client, auth_headers):
    data = _csv_bytes(
        [
            _valid_row(),
            _valid_row(nombre="Ana López", nif="87654321X"),
            _valid_row(nombre="Luis García", nif="00000000T"),
        ]
    )
    resp = client.post(
        "/api/employees/bulk-import?dry_run=false",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rows"] == 3
    assert body["valid_rows"] == 3
    assert body["created"] == 3
    assert len(body["created_ids"]) == 3
    assert body["errors"] == []
    # Comprobamos vía GET /api/employees que los 3 están.
    listed = client.get("/api/employees", headers=auth_headers)
    assert listed.status_code == 200
    nombres = {e["nombre"] for e in listed.json()}
    assert {"Juan Pérez", "Ana López", "Luis García"}.issubset(nombres)


def test_bulk_import_no_escribe_si_hay_errores_aunque_dry_run_false(client, auth_headers):
    data = _csv_bytes([_valid_row(), _valid_row(nombre="Mal", nif="X")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=false",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    body = resp.json()
    assert body["created"] == 0
    assert body["dry_run"] is True  # se fuerza si hay errores
    assert body["invalid_rows"] >= 1


def test_bulk_import_columnas_desconocidas(client, auth_headers):
    bad = b"nombre,inventada\nJuan,x\n"
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", bad, "text/csv")},
    )
    assert resp.status_code == 400
    assert "inventada" in resp.json()["detail"]


def test_bulk_import_fichero_vacio(client, auth_headers):
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", b"", "text/csv")},
    )
    assert resp.status_code == 400


def test_bulk_import_requires_auth(client):
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        files={"file": ("x.csv", b"nombre\nJuan\n", "text/csv")},
    )
    assert resp.status_code == 401


def test_bulk_import_valida_codigo_sepe(client, auth_headers):
    data = _csv_bytes([_valid_row(codigo_contrato_sepe="999")])
    resp = client.post(
        "/api/employees/bulk-import?dry_run=true",
        headers=auth_headers,
        files={"file": ("x.csv", data, "text/csv")},
    )
    body = resp.json()
    assert any(e["field"] == "codigo_contrato_sepe" for e in body["errors"])
