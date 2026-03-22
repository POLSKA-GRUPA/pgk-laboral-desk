"""Cálculo de cotizaciones a la Seguridad Social — tasas 2025.

Fuentes:
- Orden PJC/51/2025 de cotización para 2025 (Régimen General)
- Art. 119 LGSS y Disposición adicional cuarta Ley 42/2006 (AT/EP)
- RDL 2/2023 art. 127bis (MEI)

Las tasas son configurables vía data/ss_config.json para futuros ajustes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "ss_config.json"

# Topes de cotización 2025 (Régimen General)
BASE_MIN_MENSUAL_2025 = 1184.00  # SMI 2025 aprox (14 pagas)
BASE_MAX_MENSUAL_2025 = 4720.50


@dataclass(frozen=True)
class SSResult:
    """Resultado desglosado de cotización SS."""
    # Empresa
    emp_contingencias_comunes: float
    emp_desempleo: float
    emp_fogasa: float
    emp_formacion: float
    emp_mei: float
    emp_at_ep: float
    emp_total: float
    emp_pct_total: float

    # Trabajador
    trab_contingencias_comunes: float
    trab_desempleo: float
    trab_formacion: float
    trab_mei: float
    trab_total: float
    trab_pct_total: float

    # Base utilizada
    base_cotizacion: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_cotizacion_eur": round(self.base_cotizacion, 2),
            "empresa": {
                "contingencias_comunes": round(self.emp_contingencias_comunes, 2),
                "desempleo": round(self.emp_desempleo, 2),
                "fogasa": round(self.emp_fogasa, 2),
                "formacion_profesional": round(self.emp_formacion, 2),
                "mei": round(self.emp_mei, 2),
                "at_ep": round(self.emp_at_ep, 2),
                "total_eur": round(self.emp_total, 2),
                "pct_total": round(self.emp_pct_total, 4),
            },
            "trabajador": {
                "contingencias_comunes": round(self.trab_contingencias_comunes, 2),
                "desempleo": round(self.trab_desempleo, 2),
                "formacion_profesional": round(self.trab_formacion, 2),
                "mei": round(self.trab_mei, 2),
                "total_eur": round(self.trab_total, 2),
                "pct_total": round(self.trab_pct_total, 4),
            },
        }


class SSCalculator:
    """Calcula cotizaciones SS empresa y trabajador."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        self.config: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    def calculate(
        self,
        base_mensual_bruta: float,
        contract_type: str = "indefinido",
        at_ep_pct: float | None = None,
    ) -> SSResult:
        """Calcula cotizaciones mensuales sobre la base bruta mensual.

        Args:
            base_mensual_bruta: Salario bruto mensual (todos los devengos cotizables).
            contract_type: 'indefinido' o 'temporal' (afecta tasa desempleo).
            at_ep_pct: % AT/EP. Si None, usa el default de config.
        """
        cfg_emp = self.config["empresa"]
        cfg_trab = self.config["trabajador"]

        # Determinar base de cotización (con topes)
        base = self._apply_topes(base_mensual_bruta)

        # Seleccionar tasa de desempleo según tipo de contrato
        is_temporal = contract_type in (
            "temporal", "temporal-produccion", "sustitucion",
            "fijo-discontinuo", "tiempo-parcial",
        )
        emp_desempleo_pct = cfg_emp["desempleo_temporal"] if is_temporal else cfg_emp["desempleo_indefinido"]
        trab_desempleo_pct = cfg_trab["desempleo_temporal"] if is_temporal else cfg_trab["desempleo_indefinido"]

        # AT/EP
        at_ep = at_ep_pct if at_ep_pct is not None else cfg_emp["at_ep_default"]

        # --- Empresa ---
        emp_cc = base * cfg_emp["contingencias_comunes"] / 100
        emp_des = base * emp_desempleo_pct / 100
        emp_fog = base * cfg_emp["fogasa"] / 100
        emp_fp = base * cfg_emp["formacion_profesional"] / 100
        emp_mei = base * cfg_emp["mei"] / 100
        emp_at = base * at_ep / 100
        emp_total = emp_cc + emp_des + emp_fog + emp_fp + emp_mei + emp_at
        emp_pct = (emp_total / base * 100) if base else 0.0

        # --- Trabajador ---
        trab_cc = base * cfg_trab["contingencias_comunes"] / 100
        trab_des = base * trab_desempleo_pct / 100
        trab_fp = base * cfg_trab["formacion_profesional"] / 100
        trab_mei = base * cfg_trab["mei"] / 100
        trab_total = trab_cc + trab_des + trab_fp + trab_mei
        trab_pct = (trab_total / base * 100) if base else 0.0

        return SSResult(
            emp_contingencias_comunes=emp_cc,
            emp_desempleo=emp_des,
            emp_fogasa=emp_fog,
            emp_formacion=emp_fp,
            emp_mei=emp_mei,
            emp_at_ep=emp_at,
            emp_total=emp_total,
            emp_pct_total=emp_pct,
            trab_contingencias_comunes=trab_cc,
            trab_desempleo=trab_des,
            trab_formacion=trab_fp,
            trab_mei=trab_mei,
            trab_total=trab_total,
            trab_pct_total=trab_pct,
            base_cotizacion=base,
        )

    def _apply_topes(self, base: float) -> float:
        topes = self.config.get("topes", {})
        base_min = topes.get("base_min_mensual", BASE_MIN_MENSUAL_2025)
        base_max = topes.get("base_max_mensual", BASE_MAX_MENSUAL_2025)
        return max(base_min, min(base, base_max))
