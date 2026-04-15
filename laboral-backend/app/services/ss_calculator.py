"""Cálculo de cotizaciones a la Seguridad Social — tasas 2026.

Fuentes:
- Orden ISM/31/2026 (BOE-A-2026-1921) — bases cotización 2026
- RDL 3/2026 (BOE-A-2026-2548) — MEI 2026: 0,90% total (0,75% empresa + 0,15% trabajador)
- Art. 119 LGSS y DA 4ª Ley 42/2006 (AT/EP)
- DA 7ª ET — recargo contratos ≤30 días

Tasas configurables vía data/ss_config.json — última verificación: 2026-03-22 vía Perplexity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "ss_config.json"

# Topes de cotización 2026 (Régimen General) — Orden ISM/31/2026 (BOE-A-2026-1921)
BASE_MIN_MENSUAL = 1424.50  # Base mínima 2026 (= SMI 1.221€ × 14/12)
BASE_MAX_MENSUAL = 5101.20

# Recargo contratos cortos (DA 7ª ET)
_SHORT_CONTRACT_DAYS_LIMIT = 30
_SHORT_CONTRACT_SURCHARGE = 29.74


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
    grupo_cotizacion: str = ""

    # Recargo contratos cortos
    recargo_contrato_corto: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
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
        if self.grupo_cotizacion:
            d["grupo_cotizacion"] = self.grupo_cotizacion
        if self.recargo_contrato_corto > 0:
            d["recargo_contrato_corto_eur"] = round(self.recargo_contrato_corto, 2)
        return d


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
        category: str = "",
        contract_days: int | None = None,
    ) -> SSResult:
        """Calcula cotizaciones mensuales sobre la base bruta mensual.

        Args:
            base_mensual_bruta: Salario bruto mensual (todos los devengos cotizables).
            contract_type: 'indefinido' o 'temporal' (afecta tasa desempleo).
            at_ep_pct: % AT/EP. Si None, usa el default de config.
            category: Categoría del convenio (para determinar grupo de cotización).
            contract_days: Duración del contrato en días. Si ≤30, aplica recargo.
        """
        cfg_emp = self.config["empresa"]
        cfg_trab = self.config["trabajador"]

        # Determinar grupo de cotización
        grupo = self._resolve_grupo(category)

        # Determinar base de cotización (con topes por grupo)
        base = self._apply_topes(base_mensual_bruta, grupo)

        # Seleccionar tasa de desempleo según tipo de contrato
        # Fijo-discontinuo es legalmente indefinido (Art. 16 ET) → desempleo indefinido
        # "tiempo-parcial" es jornada, no tipo contrato → no afecta al desempleo
        is_temporal = contract_type in (
            "temporal",
            "temporal-produccion",
            "sustitucion",
        )
        emp_desempleo_pct = (
            cfg_emp["desempleo_temporal"] if is_temporal else cfg_emp["desempleo_indefinido"]
        )
        trab_desempleo_pct = (
            cfg_trab["desempleo_temporal"] if is_temporal else cfg_trab["desempleo_indefinido"]
        )

        # AT/EP
        at_ep = at_ep_pct if at_ep_pct is not None else cfg_emp["at_ep_default"]

        # --- Empresa ---
        emp_cc = base * cfg_emp["contingencias_comunes"] / 100
        emp_des = base * emp_desempleo_pct / 100
        emp_fog = base * cfg_emp["fogasa"] / 100
        emp_fp = base * cfg_emp["formacion_profesional"] / 100
        emp_mei = base * cfg_emp["mei"] / 100
        emp_at = base * at_ep / 100
        emp_subtotal = emp_cc + emp_des + emp_fog + emp_fp + emp_mei + emp_at
        emp_pct = (emp_subtotal / base * 100) if base else 0.0

        # --- Trabajador ---
        trab_cc = base * cfg_trab["contingencias_comunes"] / 100
        trab_des = base * trab_desempleo_pct / 100
        trab_fp = base * cfg_trab["formacion_profesional"] / 100
        trab_mei = base * cfg_trab["mei"] / 100
        trab_total = trab_cc + trab_des + trab_fp + trab_mei
        trab_pct = (trab_total / base * 100) if base else 0.0

        # --- Recargo contratos cortos (DA 7ª ET) ---
        recargo = self._short_contract_surcharge(contract_days)
        # El total empresa incluye el recargo si aplica
        emp_total = emp_subtotal + recargo

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
            grupo_cotizacion=grupo,
            recargo_contrato_corto=recargo,
        )

    def _resolve_grupo(self, category: str) -> str:
        """Resuelve el grupo de cotización SS a partir de la categoría del convenio."""
        mapa = self.config.get("mapa_categoria_grupo", {})
        grupo = mapa.get(category, "")
        if not grupo:
            # Intentar sin punto final
            grupo = mapa.get(category.rstrip("."), "")
        return grupo

    def _apply_topes(self, base: float, grupo: str = "") -> float:
        """Aplica topes de cotización. Si hay grupo, usa bases específicas del grupo."""
        grupos_cfg = self.config.get("grupos_cotizacion", {})
        if grupo and grupo in grupos_cfg:
            g = grupos_cfg[grupo]
            base_min = g["base_min"]
            base_max = g["base_max"]
            # Grupos 8-11 tienen bases diarias: convertir a mensual (×30)
            if g.get("_diario"):
                base_min *= 30
                base_max *= 30
        else:
            topes = self.config.get("topes", {})
            base_min = topes.get("base_min_mensual", BASE_MIN_MENSUAL)
            base_max = topes.get("base_max_mensual", BASE_MAX_MENSUAL)
        return max(base_min, min(base, base_max))

    def _short_contract_surcharge(self, contract_days: int | None) -> float:
        """Recargo adicional para contratos de duración ≤30 días (DA 7ª ET)."""
        if contract_days is None or contract_days <= 0:
            return 0.0
        cfg = self.config.get("recargo_contratos_cortos", {})
        limit = cfg.get("dias_limite", _SHORT_CONTRACT_DAYS_LIMIT)
        surcharge = cfg.get("importe_eur", _SHORT_CONTRACT_SURCHARGE)
        if contract_days <= limit:
            return surcharge
        return 0.0
