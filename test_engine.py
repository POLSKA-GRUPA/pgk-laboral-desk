"""Tests para PGK Laboral Desk — motor, SS e IRPF."""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import LaboralEngine
from ss_calculator import SSCalculator
from irpf_estimator import IRPFEstimator


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
    # Base below minimum should be capped up
    result_low = ss.calculate(base_mensual_bruta=500.0)
    assert result_low.base_cotizacion >= 1184.0
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
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"
