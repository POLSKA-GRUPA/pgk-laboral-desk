"""Estimación de retención IRPF — 2026.

Escalas separadas: estatal + autonómica (por CC.AA.).
CC.AA. soportadas: Madrid, Cataluña, Andalucía, C. Valenciana + genérica.

NOTA: Cálculo ORIENTATIVO. El tipo definitivo depende de la situación
personal y familiar completa del contribuyente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ======================================================================
# Escalas IRPF 2026
# ======================================================================

# Escala estatal (igual para todas las CC.AA.)
_STATE_BRACKETS: list[tuple[float, float]] = [
    (12_450.0, 0.095),
    (20_200.0, 0.12),
    (35_200.0, 0.15),
    (60_000.0, 0.185),
    (300_000.0, 0.225),
    (float("inf"), 0.245),
]

# Escalas autonómicas
_REGIONAL_BRACKETS: dict[str, list[tuple[float, float]]] = {
    "madrid": [
        (12_450.0, 0.085),
        (17_707.2, 0.1070),
        (33_007.2, 0.1280),
        (53_407.2, 0.1790),
        (float("inf"), 0.2060),
    ],
    "cataluna": [
        (12_450.0, 0.105),
        (17_707.2, 0.12),
        (33_007.2, 0.15),
        (53_407.2, 0.185),
        (90_000.0, 0.2125),
        (120_000.0, 0.2350),
        (175_000.0, 0.2450),
        (float("inf"), 0.255),
    ],
    "andalucia": [
        (12_450.0, 0.095),
        (20_200.0, 0.12),
        (28_000.0, 0.15),
        (35_200.0, 0.155),
        (50_000.0, 0.185),
        (60_000.0, 0.1850),
        (120_000.0, 0.225),
        (float("inf"), 0.245),
    ],
    "valencia": [
        (12_450.0, 0.10),
        (17_707.2, 0.12),
        (33_007.2, 0.14),
        (53_407.2, 0.18),
        (80_000.0, 0.225),
        (120_000.0, 0.245),
        (175_000.0, 0.255),
        (float("inf"), 0.295),
    ],
}

# Genérica: aproximación media = misma que estatal (50/50)
_REGIONAL_BRACKETS["generica"] = _STATE_BRACKETS

SUPPORTED_REGIONS = ["generica", "madrid", "cataluna", "andalucia", "valencia"]


# ======================================================================
# Constantes
# ======================================================================

_PERSONAL_MINIMUM = 5_550.0
_CHILD_MINIMUMS = [2_400.0, 2_700.0, 4_000.0, 4_500.0]
_CHILD_UNDER_3_EXTRA = 2_800.0
_OTHER_WORK_EXPENSES = 2_000.0
_MIN_RETENTION_TEMPORAL = 2.0
_MIN_RETENTION_GENERAL = 0.0


# ======================================================================
# Resultado
# ======================================================================


@dataclass(frozen=True)
class IRPFResult:
    annual_gross: float
    annual_ss_worker: float
    taxable_base: float
    work_reduction: float
    personal_family_minimum: float
    tax_on_income: float
    tax_on_minimum: float
    annual_retention: float
    retention_rate_pct: float
    monthly_retention: float
    region: str = "generica"
    is_estimate: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "bruto_anual_eur": round(self.annual_gross, 2),
            "ss_trabajador_anual_eur": round(self.annual_ss_worker, 2),
            "base_liquidable_eur": round(self.taxable_base, 2),
            "reduccion_rendimientos_trabajo_eur": round(self.work_reduction, 2),
            "minimo_personal_familiar_eur": round(self.personal_family_minimum, 2),
            "cuota_sobre_renta_eur": round(self.tax_on_income, 2),
            "cuota_sobre_minimo_eur": round(self.tax_on_minimum, 2),
            "retencion_anual_eur": round(self.annual_retention, 2),
            "tipo_retencion_pct": round(self.retention_rate_pct, 2),
            "retencion_mensual_eur": round(self.monthly_retention, 2),
            "comunidad_autonoma": self.region,
            "es_estimacion": True,
        }


# ======================================================================
# Estimador
# ======================================================================


class IRPFEstimator:
    def estimate(
        self,
        annual_gross: float,
        annual_ss_worker: float,
        num_children: int = 0,
        children_under_3: int = 0,
        contract_type: str = "indefinido",
        num_payments: int = 14,
        region: str = "generica",
    ) -> IRPFResult:
        # Rendimiento neto
        net_income = max(annual_gross - annual_ss_worker - _OTHER_WORK_EXPENSES, 0.0)

        # Reducción rendimientos del trabajo
        work_reduction = self._work_income_reduction(net_income)

        # Base liquidable
        taxable_base = max(net_income - work_reduction, 0.0)

        # Mínimo personal y familiar
        personal_minimum = self._personal_family_minimum(num_children, children_under_3)

        # Cuotas: estatal + autonómica
        region_key = region.lower().replace("ñ", "n").replace("í", "i").replace("á", "a")
        if region_key not in _REGIONAL_BRACKETS:
            region_key = "generica"

        tax_state = self._apply_scale(taxable_base, _STATE_BRACKETS)
        tax_region = self._apply_scale(taxable_base, _REGIONAL_BRACKETS[region_key])
        tax_on_income = tax_state + tax_region

        min_state = self._apply_scale(personal_minimum, _STATE_BRACKETS)
        min_region = self._apply_scale(personal_minimum, _REGIONAL_BRACKETS[region_key])
        tax_on_minimum = min_state + min_region

        # Retención
        annual_retention = max(tax_on_income - tax_on_minimum, 0.0)
        retention_rate = (annual_retention / annual_gross * 100) if annual_gross > 0 else 0.0

        # Mínimo de retención
        is_temporal = contract_type in ("temporal", "temporal-produccion", "sustitucion")
        min_rate = _MIN_RETENTION_TEMPORAL if is_temporal else _MIN_RETENTION_GENERAL
        retention_rate = max(retention_rate, min_rate)

        annual_retention = annual_gross * retention_rate / 100
        monthly_retention = annual_retention / num_payments

        return IRPFResult(
            annual_gross=annual_gross,
            annual_ss_worker=annual_ss_worker,
            taxable_base=taxable_base,
            work_reduction=work_reduction,
            personal_family_minimum=personal_minimum,
            tax_on_income=tax_on_income,
            tax_on_minimum=tax_on_minimum,
            annual_retention=annual_retention,
            retention_rate_pct=retention_rate,
            monthly_retention=monthly_retention,
            region=region_key,
        )

    @staticmethod
    def _work_income_reduction(net_income: float) -> float:
        if net_income <= 14_852.0:
            return 7_302.0
        if net_income <= 17_673.52:
            return 7_302.0 - 1.75 * (net_income - 14_852.0)
        return 2_364.34

    @staticmethod
    def _personal_family_minimum(num_children: int, children_under_3: int) -> float:
        total = _PERSONAL_MINIMUM
        for i in range(num_children):
            idx = min(i, len(_CHILD_MINIMUMS) - 1)
            total += _CHILD_MINIMUMS[idx]
        total += children_under_3 * _CHILD_UNDER_3_EXTRA
        return total

    @staticmethod
    def _apply_scale(amount: float, brackets: list[tuple[float, float]]) -> float:
        tax = 0.0
        prev_limit = 0.0
        for limit, rate in brackets:
            chunk = min(amount, limit) - prev_limit
            if chunk <= 0:
                break
            tax += chunk * rate
            prev_limit = limit
        return tax
