from __future__ import annotations

from engine import LaboralEngine


def build_engine() -> LaboralEngine:
    return LaboralEngine.from_json_file("data/convenio_acuaticas_2025_2027.json")


def test_socorrista_b_ready() -> None:
    engine = build_engine()
    result = engine.analyze(
        "Quiero contratar un socorrista nivel B fijo discontinuo a 40 horas semanales para la temporada de verano."
    )
    assert result["status"] == "ready"
    assert result["request"]["category_match"]["row"]["category"] == "Nivel B."
    assert result["payroll_draft"]["totals"]["total_devengado_convenio_eur"] == 1318.85


def test_auxiliar_with_seniority() -> None:
    engine = build_engine()
    result = engine.analyze(
        "Necesito un auxiliar administrativo indefinido a jornada completa y con 6 años de antigüedad acumulada."
    )
    assert result["status"] == "ready"
    assert result["request"]["trienios"] == 2
    assert result["payroll_draft"]["totals"]["total_devengado_convenio_eur"] == 1389.89


def test_missing_hours_requires_clarification() -> None:
    engine = build_engine()
    result = engine.analyze("Quiero contratar un conductor especialista fijo discontinuo.")
    assert result["status"] == "needs_clarification"
    assert result["payroll_draft"] is None
    assert result["clarifications"]


def test_socorrista_generic_does_not_fail_as_missing() -> None:
    engine = build_engine()
    result = engine.analyze("socorrista media jornada fijo descontinuo")
    assert result["status"] == "needs_clarification"
    assert result["request"]["contract_type"] == "fijo-discontinuo"
    assert result["request"]["category_match"]["status"] == "ambiguous"
    assert "Nivel B." in result["request"]["category_match"]["alternatives"]
