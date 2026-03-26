"""Tests para el parser conversacional."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chat_parser import ChatParser


def make_parser():
    return ChatParser()


# --- Match exacto ---


def test_match_limpiador():
    p = make_parser()
    r = p.parse("Necesito alguien para limpiar la piscina a jornada completa indefinido")
    assert r["action"] == "ready"
    assert r["params"]["category"] == "Limpiador de piscinas."


def test_match_electricista():
    p = make_parser()
    r = p.parse("Quiero contratar un electricista a 40 horas indefinido")
    assert r["action"] == "ready"
    assert r["params"]["category"] == "Instalador de montajes eléctricos."


def test_match_monitor():
    p = make_parser()
    r = p.parse("Necesito un monitor de natación a media jornada temporal")
    assert r["action"] == "ready"
    assert r["params"]["category"] == "Monitor de natación."
    assert r["params"]["weekly_hours"] == 20.0


def test_match_comercial():
    p = make_parser()
    r = p.parse("Quiero un comercial para ventas a jornada completa indefinido")
    assert r["action"] == "ready"
    assert r["params"]["category"] == "Comercial."


# --- Familias ambiguas ---


def test_socorrista_ambiguo():
    p = make_parser()
    r = p.parse("Necesito un socorrista")
    assert r["action"] == "clarify_category"
    assert len(r["options"]) == 4


def test_socorrista_nivel_a_resuelto():
    p = make_parser()
    r = p.parse("Quiero un socorrista nivel A para coordinar a jornada completa indefinido")
    assert r["action"] == "ready"
    assert r["params"]["category"] == "Nivel A."


def test_socorrista_correturnos():
    p = make_parser()
    r = p.parse("Necesito un socorrista sustituto para cubrir turnos jornada completa temporal")
    assert r["action"] == "ready"
    assert r["params"]["category"] == "Socorrista correturnos."


def test_administrativo_ambiguo():
    p = make_parser()
    r = p.parse("Necesito un administrativo")
    assert r["action"] == "clarify_category"
    assert len(r["options"]) == 3


def test_administrativo_jefe_resuelto():
    p = make_parser()
    r = p.parse("Necesito un jefe administrativo a jornada completa indefinido")
    assert r["action"] == "ready"
    assert r["params"]["category"] == "Jefe Administrativo."


# --- Parámetros faltantes ---


def test_falta_jornada_y_contrato():
    p = make_parser()
    r = p.parse("Necesito un almacenero")
    assert r["action"] == "need_params"
    assert "jornada" in r.get("missing", [])
    assert "contract_type" in r.get("missing", [])


def test_falta_solo_contrato():
    p = make_parser()
    r = p.parse("Necesito un almacenero a jornada completa")
    assert r["action"] == "need_params"
    assert "contract_type" in r.get("missing", [])


# --- Flujo multi-turno ---


def test_multiturn_socorrista():
    p = make_parser()
    # Turno 1: ambiguo
    r1 = p.parse("Quiero un socorrista para verano")
    assert r1["action"] == "clarify_category"
    ctx = r1["context"]

    # Turno 2: elige nivel B
    r2 = p.parse("Nivel B", ctx)
    # Podría pedir parámetros o dar resultado (verano -> podría parsear temporal)
    assert r2["action"] in ("need_params", "ready")


def test_multiturn_params():
    p = make_parser()
    # Turno 1: categoría clara pero faltan datos
    r1 = p.parse("Quiero un encargado")
    assert r1["action"] == "need_params"
    ctx = r1["context"]

    # Turno 2: completar datos
    r2 = p.parse("Jornada completa, indefinido", ctx)
    assert r2["action"] == "ready"
    assert r2["params"]["weekly_hours"] == 40.0
    assert r2["params"]["contract_type"] == "indefinido"


# --- Extractores ---


def test_extract_hours_media_jornada():
    p = make_parser()
    r = p.parse("Un limpiador a media jornada indefinido")
    assert r["action"] == "ready"
    assert r["params"]["weekly_hours"] == 20.0


def test_extract_hours_percentage():
    p = make_parser()
    r = p.parse("Limpiador al 75% indefinido")
    assert r["action"] == "ready"
    assert r["params"]["weekly_hours"] == 30.0


def test_extract_seniority():
    p = make_parser()
    r = p.parse("Limpiador a jornada completa indefinido con 6 años de antigüedad")
    assert r["action"] == "ready"
    assert r["params"]["seniority_years"] == 6


def test_extract_extras_prorated():
    p = make_parser()
    r = p.parse("Limpiador jornada completa indefinido con 12 pagas")
    assert r["action"] == "ready"
    assert r["params"]["extras_prorated"] is True


# --- Caso no encontrado ---


def test_not_found():
    p = make_parser()
    r = p.parse("asdfghjkl")
    assert r["action"] == "not_found"
