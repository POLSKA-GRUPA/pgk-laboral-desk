"""Tests para client_manager y convenio_verifier."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from client_manager import ClientManager
from convenio_verifier import ConvenioVerifier, VerificationResult


# ======================================================================
# ClientManager
# ======================================================================

@pytest.fixture
def cm(tmp_path):
    db = tmp_path / "test.db"
    mgr = ClientManager(db_path=db)
    mgr.init_tables()
    return mgr


def test_list_convenios():
    convenios = ClientManager.list_convenios()
    assert len(convenios) >= 2
    ids = [c["id"] for c in convenios]
    assert "convenio_acuaticas_2025_2027" in ids
    assert "convenio_oficinas_despachos_alicante_2024_2026" in ids


def test_register_and_get_client(cm):
    cid = cm.register_client(
        empresa="Despacho Test S.L.",
        cif="B12345678",
        convenio_id="convenio_oficinas_despachos_alicante_2024_2026",
        provincia="Alicante",
        comunidad_autonoma="Comunitat Valenciana",
    )
    assert cid > 0
    client = cm.get_client(cid)
    assert client is not None
    assert client.empresa == "Despacho Test S.L."
    assert client.cif == "B12345678"
    assert "Oficinas" in client.convenio_nombre


def test_get_client_by_cif(cm):
    cm.register_client(
        empresa="Empresa CIF Test",
        cif="A99887766",
        convenio_id="convenio_acuaticas_2025_2027",
    )
    client = cm.get_client_by_cif("a99887766")  # lowercase
    assert client is not None
    assert client.empresa == "Empresa CIF Test"


def test_list_clients(cm):
    cm.register_client(empresa="AAA", cif="B11111111", convenio_id="convenio_acuaticas_2025_2027")
    cm.register_client(empresa="BBB", cif="B22222222", convenio_id="convenio_acuaticas_2025_2027")
    clients = cm.list_clients()
    assert len(clients) == 2
    assert clients[0]["empresa"] == "AAA"


def test_duplicate_cif_raises(cm):
    cm.register_client(empresa="First", cif="B33333333", convenio_id="convenio_acuaticas_2025_2027")
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        cm.register_client(empresa="Second", cif="B33333333", convenio_id="convenio_acuaticas_2025_2027")


def test_invalid_cif_raises(cm):
    with pytest.raises(ValueError, match="no válido"):
        cm.register_client(empresa="Bad", cif="INVALID", convenio_id="convenio_acuaticas_2025_2027")


def test_invalid_convenio_raises(cm):
    with pytest.raises(ValueError, match="no encontrado"):
        cm.register_client(empresa="Bad", cif="B44444444", convenio_id="convenio_inexistente")


def test_update_convenio(cm):
    cid = cm.register_client(
        empresa="Cambio Conv",
        cif="B55555555",
        convenio_id="convenio_acuaticas_2025_2027",
    )
    cm.update_convenio(cid, "convenio_oficinas_despachos_alicante_2024_2026")
    client = cm.get_client(cid)
    assert "Oficinas" in client.convenio_nombre


# ======================================================================
# CIF validation
# ======================================================================

def test_valid_cif_formats():
    v = ClientManager.validate_cif
    assert v("B12345678")   # CIF empresa
    assert v("A00000000")   # CIF asociación
    assert v("12345678Z")   # NIF persona
    assert v("X1234567L")   # NIE


def test_invalid_cif_formats():
    v = ClientManager.validate_cif
    assert not v("INVALID")
    assert not v("123")
    assert not v("B1234")       # too short
    assert not v("B123456789")  # too long


# ======================================================================
# ConvenioVerifier — offline
# ======================================================================

def test_verifier_unavailable_without_key():
    v = ConvenioVerifier(api_key="")
    result = v.verify("test", "test")
    assert result.status == "unavailable"
    assert result.is_advisory is True


def test_verifier_parse_verified():
    raw = '{"nombre": "Conv Test", "vigencia_hasta": 2026, "fuente": "BOP"}'
    result = ConvenioVerifier._parse_response(raw, our_vigencia=2026)
    assert result.status == "verified"


def test_verifier_parse_outdated():
    raw = '{"nombre": "Conv Nuevo", "vigencia_hasta": 2028, "fuente": "BOE"}'
    result = ConvenioVerifier._parse_response(raw, our_vigencia=2026)
    assert result.status == "outdated"
    assert "2028" in result.message


def test_verifier_parse_uncertain():
    raw = '{"status": "uncertain"}'
    result = ConvenioVerifier._parse_response(raw, our_vigencia=2026)
    assert result.status == "uncertain"


def test_verifier_parse_bad_json():
    raw = "This is not JSON at all"
    result = ConvenioVerifier._parse_response(raw, our_vigencia=2026)
    assert result.status == "uncertain"


def test_verifier_parse_markdown_wrapped():
    raw = '```json\n{"nombre": "Test", "vigencia_hasta": 2026, "fuente": "BOP"}\n```'
    result = ConvenioVerifier._parse_response(raw, our_vigencia=2026)
    assert result.status == "verified"


# ======================================================================
# ConvenioVerifier — integración real (requiere API key)
# ======================================================================

@pytest.mark.integration
def test_verifier_real_oficinas():
    """Verifica el convenio de oficinas y despachos contra Perplexity."""
    v = ConvenioVerifier()
    if not v.available:
        pytest.skip("PERPLEXITY_API_KEY no configurada")
    result = v.verify(
        sector="Oficinas y Despachos",
        provincia="Alicante",
        codigo_convenio="03001005011983",
        vigencia_hasta=2026,
    )
    assert result.status in ("verified", "uncertain")
    assert result.is_advisory is True
