"""Regression tests for `app.mcp.server` fail-fast behavior.

Respuesta a Devin Review en PR #16 (beta-3..6): los hardcoded
"1424.50"/"5101.20"/"4.70"/"23.60"/etc. en `_ss_rate` / topes violaban
AGENTS.md regla 8. Tras portar el patron fail-fast de PR #15 a esta copia,
verificamos que:

  - `_load_ss_config` RAISE si falta el JSON (no devuelve fallback).
  - `_ss_rate(section, key)` ya no acepta `fallback` como 3er arg.
  - `_ss_topes()` existe y lee todo del config.
"""

from __future__ import annotations

import inspect

from app.mcp import server


def test_beta3_load_ss_config_raises_on_missing_file(tmp_path, monkeypatch):
    """beta-3: ss_config.json ausente debe fallar ruidosamente."""
    monkeypatch.setattr(server, "_SS_CONFIG_PATH", tmp_path / "no_existe.json")
    try:
        server._load_ss_config()
    except RuntimeError as e:
        assert "ss_config.json" in str(e) or "no_existe.json" in str(e)
    else:
        raise AssertionError("regresión beta-3: _load_ss_config devolvió fallback en vez de raise")


def test_beta3_ss_rate_has_no_fallback_parameter():
    """beta-4/5/6: `_ss_rate(section, key, fallback)` → firma sin fallback."""
    sig = inspect.signature(server._ss_rate)
    params = list(sig.parameters)
    assert params == ["section", "key"], (
        f"regresión beta-4..6: _ss_rate re-introdujo fallback. Firma actual: {params}"
    )


def test_beta3_ss_topes_reads_from_config():
    """Los topes deben salir del `_ss_topes()` helper, no de literales."""
    assert hasattr(server, "_ss_topes"), "falta helper _ss_topes"
    base_min, base_max = server._ss_topes()
    # Vienen de data/ss_config.json. No asertamos el valor (se actualiza
    # anualmente); solo que son positivos y min < max.
    assert base_min > 0
    assert base_max > base_min


def test_beta3_no_hardcoded_topes_in_calcular_nomina():
    """El source de _calcular_nomina no debe contener los literales prohibidos."""
    src = inspect.getsource(server._calcular_nomina)
    for forbidden in ('"1424.50"', '"5101.20"', '"4.70"', '"1.55"', '"0.10"'):
        assert forbidden not in src, (
            f"regresión beta-4: literal {forbidden} volvió a _calcular_nomina"
        )


def test_zeta1_no_stale_legal_citation_in_mcp_package():
    """zeta-1 (3rd review PR #16): ni `server.py` ni `server_main.py` deben
    referenciar la Orden ISM/31/2026 (pescadores, BOE-A-2026-1921). La cita
    correcta para el Regimen General 2026 es Orden PJC/297/2026
    (BOE-A-2026-7296). Un host IA leyendo la `description` del resource
    `laboral://seguridad-social` veria la ley erronea.
    """
    from pathlib import Path

    mcp_dir = Path(server.__file__).parent
    for name in ("server.py", "server_main.py"):
        src = (mcp_dir / name).read_text(encoding="utf-8")
        for forbidden in ("ISM/31/2026", "BOE-A-2026-1921"):
            assert forbidden not in src, (
                f"regresión zeta-1: {name} sigue citando '{forbidden}'. "
                f"Usa Orden PJC/297/2026 (BOE-A-2026-7296)."
            )


def test_beta3_no_hardcoded_rates_in_calcular_ss():
    """Mismo check sobre _calcular_ss (tasas empresa)."""
    src = inspect.getsource(server._calcular_ss)
    for forbidden in (
        '"1424.50"',
        '"5101.20"',
        '"23.60"',
        '"5.50"',
        '"6.70"',
        '"0.60"',
        '"0.20"',
        '"0.75"',
    ):
        assert forbidden not in src, (
            f"regresión beta-5/6: literal {forbidden} volvió a _calcular_ss"
        )
