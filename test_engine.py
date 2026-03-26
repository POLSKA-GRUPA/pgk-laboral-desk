"""Tests para PGK Laboral Desk — motor, SS e IRPF."""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import LaboralEngine
from irpf_estimator import IRPFEstimator
from ss_calculator import SSCalculator


def test_ss_calculator_indefinido():
    ss = SSCalculator()
    result = ss.calculate(base_mensual_bruta=1318.85, contract_type="indefinido")
    # Empresa total should be ~30-33% of base
    assert result.emp_total > 0
    assert 30 < result.emp_pct_total < 34
    # Trabajador total ~6.3-6.6%
    assert 6 < result.trab_pct_total < 7


def test_ss_calculator_temporal():
    ss = SSCalculator()
    result = ss.calculate(base_mensual_bruta=1318.85, contract_type="temporal")
    # Temporal has higher desempleo
    assert result.emp_pct_total > 31


def test_ss_topes():
    ss = SSCalculator()
    # Base below minimum should be capped up (2026: 1323€)
    result_low = ss.calculate(base_mensual_bruta=500.0)
    assert result_low.base_cotizacion >= 1323.0
    # Base above maximum should be capped down
    result_high = ss.calculate(base_mensual_bruta=6000.0)
    assert result_high.base_cotizacion <= 4720.50


def test_irpf_low_salary():
    irpf = IRPFEstimator()
    # Low salary should have very low or 0% retention
    result = irpf.estimate(annual_gross=14000.0, annual_ss_worker=900.0)
    assert result.retention_rate_pct < 5


def test_irpf_medium_salary():
    irpf = IRPFEstimator()
    result = irpf.estimate(annual_gross=25000.0, annual_ss_worker=1600.0)
    assert 5 < result.retention_rate_pct < 20


def test_irpf_with_children():
    irpf = IRPFEstimator()
    no_kids = irpf.estimate(annual_gross=25000.0, annual_ss_worker=1600.0)
    with_kids = irpf.estimate(annual_gross=25000.0, annual_ss_worker=1600.0, num_children=2)
    # Children should reduce retention
    assert with_kids.retention_rate_pct < no_kids.retention_rate_pct


def test_engine_simulate_basic():
    engine = LaboralEngine.from_json_file()
    result = engine.simulate(
        category="Nivel B.",
        contract_type="indefinido",
        weekly_hours=40.0,
    )
    assert "error" not in result
    assert result["bruto_mensual_eur"] > 0
    assert result["coste_total_empresa_mes_eur"] > result["bruto_mensual_eur"]
    assert result["neto_mensual_eur"] < result["bruto_mensual_eur"]
    assert result["neto_mensual_eur"] > 0


def test_engine_simulate_part_time():
    engine = LaboralEngine.from_json_file()
    full = engine.simulate(category="Nivel B.", weekly_hours=40.0)
    half = engine.simulate(category="Nivel B.", weekly_hours=20.0)
    assert half["bruto_mensual_eur"] < full["bruto_mensual_eur"]


def test_engine_simulate_seniority():
    engine = LaboralEngine.from_json_file()
    no_sen = engine.simulate(category="Nivel B.", seniority_years=0)
    with_sen = engine.simulate(category="Nivel B.", seniority_years=6)  # 2 trienios
    assert with_sen["bruto_mensual_eur"] > no_sen["bruto_mensual_eur"]


def test_engine_simulate_prorated():
    engine = LaboralEngine.from_json_file()
    r14 = engine.simulate(category="Nivel B.", extras_prorated=False)
    r12 = engine.simulate(category="Nivel B.", extras_prorated=True)
    # Prorated monthly should be higher (includes prorrata)
    assert r12["bruto_mensual_eur"] > r14["bruto_mensual_eur"]


def test_engine_categories_list():
    engine = LaboralEngine.from_json_file()
    cats = engine.get_categories()
    assert len(cats) == 24
    assert any(c["value"] == "Nivel B." for c in cats)


def test_engine_unknown_category():
    engine = LaboralEngine.from_json_file()
    result = engine.simulate(category="Categoría inventada")
    assert "error" in result


def test_engine_result_structure():
    """Verifica que el resultado tiene todas las claves necesarias."""
    engine = LaboralEngine.from_json_file()
    result = engine.simulate(category="Nivel B.")
    required_keys = [
        "coste_total_empresa_mes_eur",
        "coste_total_empresa_anual_eur",
        "bruto_mensual_eur",
        "neto_mensual_eur",
        "ss_empresa_mes_eur",
        "ss_trabajador_mes_eur",
        "irpf_retencion_pct",
        "irpf_mensual_eur",
        "devengos",
        "ss_detalle",
        "irpf_detalle",
        "notas",
        "fuentes",
        "grupo_cotizacion_ss",
        "region_irpf",
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"


# ======================================================================
# Tests 2026: IRPF regional, recargo contratos cortos, grupo SS
# ======================================================================


def test_irpf_regional_madrid_lower_than_cataluna():
    """Madrid tiene tipos más bajos que Cataluña."""
    irpf = IRPFEstimator()
    madrid = irpf.estimate(annual_gross=35000.0, annual_ss_worker=2300.0, region="madrid")
    cataluna = irpf.estimate(annual_gross=35000.0, annual_ss_worker=2300.0, region="cataluña")
    assert madrid.retention_rate_pct < cataluna.retention_rate_pct
    assert madrid.region == "madrid"
    assert cataluna.region == "cataluna"  # normalized


def test_irpf_generica_is_default():
    irpf = IRPFEstimator()
    result = irpf.estimate(annual_gross=30000.0, annual_ss_worker=2000.0)
    assert result.region == "generica"


def test_ss_grupo_cotizacion():
    """Nivel B. debe mapearse a grupo 6 (Subalternos)."""
    ss = SSCalculator()
    result = ss.calculate(base_mensual_bruta=1318.85, category="Nivel B.")
    assert result.grupo_cotizacion == "6"


def test_ss_grupo_tecnico_titulado():
    """Técnico Titulado → grupo 1 con base mínima 1903.50."""
    ss = SSCalculator()
    result = ss.calculate(base_mensual_bruta=1500.0, category="Técnico Titulado.")
    assert result.grupo_cotizacion == "1"
    # Base should be capped UP to grupo 1 minimum (1903.50)
    assert result.base_cotizacion >= 1903.0


def test_ss_recargo_contrato_corto():
    ss = SSCalculator()
    result_short = ss.calculate(base_mensual_bruta=1400.0, contract_days=15)
    result_long = ss.calculate(base_mensual_bruta=1400.0, contract_days=60)
    result_none = ss.calculate(base_mensual_bruta=1400.0)
    assert result_short.recargo_contrato_corto > 0
    assert result_long.recargo_contrato_corto == 0.0
    assert result_none.recargo_contrato_corto == 0.0


def test_ss_recargo_in_dict():
    ss = SSCalculator()
    result = ss.calculate(base_mensual_bruta=1400.0, contract_days=20)
    d = result.to_dict()
    assert "recargo_contrato_corto_eur" in d
    assert d["recargo_contrato_corto_eur"] == 29.74


def test_engine_simulate_with_region():
    engine = LaboralEngine.from_json_file()
    result = engine.simulate(category="Nivel B.", region="madrid")
    assert result["region_irpf"] == "madrid"
    # Should mention autonomic scale in notas
    assert any("madrid" in n.lower() for n in result["notas"])


def test_engine_simulate_short_contract():
    engine = LaboralEngine.from_json_file()
    result = engine.simulate(category="Nivel B.", contract_type="temporal", contract_days=15)
    # Should include surcharge note
    assert any("recargo" in n.lower() for n in result["notas"])


def test_engine_regions_list():
    engine = LaboralEngine.from_json_file()
    regions = engine.get_regions()
    assert len(regions) >= 5
    values = [r["value"] for r in regions]
    assert "madrid" in values
    assert "generica" in values


# ======================================================================
# Tests multi-convenio: oficinas y despachos Alicante
# ======================================================================


def test_engine_oficinas_loads():
    engine = LaboralEngine.from_convenio_id("convenio_oficinas_despachos_alicante_2024_2026")
    cats = engine.get_categories()
    assert len(cats) >= 20
    assert engine._convenio_pagas == 15  # 3 extras + 12


def test_engine_oficinas_simulate_grupo4():
    engine = LaboralEngine.from_convenio_id("convenio_oficinas_despachos_alicante_2024_2026")
    result = engine.simulate(
        category="Grupo 4 Nivel 1 \u2014 Jefe Adm\u00f3n. 2\u00aa / Cajero firma / Secretario Direcci\u00f3n",
        contract_type="indefinido",
        weekly_hours=40.0,
    )
    assert "error" not in result
    assert result["bruto_mensual_eur"] > 0
    assert result["neto_mensual_eur"] > 0
    assert result["pagas"] == "15"
    # Convenio should be oficinas
    assert "Oficinas" in result["convenio"]["nombre"]


def test_engine_oficinas_simulate_grupo6():
    engine = LaboralEngine.from_convenio_id("convenio_oficinas_despachos_alicante_2024_2026")
    result = engine.simulate(
        category="Grupo 6 Nivel 1 \u2014 Auxiliar adm\u00f3n. (>3 a\u00f1os) / Recepcionista",
    )
    assert "error" not in result
    assert result["bruto_mensual_eur"] > 0


def test_engine_oficinas_15_pagas_anual():
    """Con 15 pagas, el bruto anual debe ser ~15x el mensual base."""
    engine = LaboralEngine.from_convenio_id("convenio_oficinas_despachos_alicante_2024_2026")
    result = engine.simulate(
        category="Grupo 1 Nivel 1 \u2014 Titulado Superior (desde 3er a\u00f1o)",
    )
    assert "error" not in result
    # Anual should be roughly 15 * mensual (plus transporte adds a bit)
    ratio = result["bruto_anual_eur"] / result["bruto_mensual_eur"]
    assert 14 < ratio < 16


def test_engine_list_available_convenios():
    convenios = LaboralEngine.list_available_convenios()
    assert len(convenios) >= 2
    ids = [c["id"] for c in convenios]
    assert "convenio_acuaticas_2025_2027" in ids
    assert "convenio_oficinas_despachos_alicante_2024_2026" in ids


def test_engine_from_convenio_id_not_found():
    import pytest

    with pytest.raises(FileNotFoundError):
        LaboralEngine.from_convenio_id("convenio_inexistente")
