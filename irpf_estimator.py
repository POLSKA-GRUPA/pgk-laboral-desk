"""Estimación de retención IRPF sobre rendimientos del trabajo — 2025.

Implementa el algoritmo simplificado de la AEAT para cálculo del tipo
de retención (arts. 80-86 RIRPF, RD 439/2007 modificado).

NOTA: Este cálculo es ORIENTATIVO.  El tipo definitivo depende de la
situación personal y familiar completa del contribuyente.

Escala general 2025 (estatal + CC.AA. media):
  0 – 12.450 €        → 19 %
  12.450 – 20.200 €   → 24 %
  20.200 – 35.200 €   → 30 %
  35.200 – 60.000 €   → 37 %
  60.000 – 300.000 €  → 45 %
  > 300.000 €         → 47 %
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Escala general combinada (estado + CC.AA. media) — 2025
_BRACKETS: list[tuple[float, float]] = [
    (12_450.0, 0.19),
    (20_200.0, 0.24),
    (35_200.0, 0.30),
    (60_000.0, 0.37),
    (300_000.0, 0.45),
    (float("inf"), 0.47),
]

# Mínimo personal y familiar (art. 57-61 LIRPF)
_PERSONAL_MINIMUM = 5_550.0
_CHILD_MINIMUMS = [2_400.0, 2_700.0, 4_000.0, 4_500.0]  # 1º, 2º, 3º, 4º+
_CHILD_UNDER_3_EXTRA = 2_800.0

# Otros gastos deducibles del rendimiento del trabajo (art. 19.2 LIRPF)
_OTHER_WORK_EXPENSES = 2_000.0

# Mínimos de retención
_MIN_RETENTION_TEMPORAL = 2.0  # % mínimo para contratos temporales < 1 año
_MIN_RETENTION_GENERAL = 0.0


@dataclass(frozen=True)
class IRPFResult:
    """Resultado del cálculo estimado de retención IRPF."""
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
            "es_estimacion": True,
        }


class IRPFEstimator:
    """Calcula el tipo de retención estimado de IRPF."""

    def estimate(
        self,
        annual_gross: float,
        annual_ss_worker: float,
        num_children: int = 0,
        children_under_3: int = 0,
        contract_type: str = "indefinido",
        num_payments: int = 14,
    ) -> IRPFResult:
        """Estima la retención mensual de IRPF.

        Args:
            annual_gross: Retribución bruta anual (salario + extras).
            annual_ss_worker: Cotización anual del trabajador a SS.
            num_children: Número de hijos a cargo (< 25 años o discapacitados).
            children_under_3: De esos hijos, cuántos son menores de 3 años.
            contract_type: Tipo de contrato (afecta retención mínima).
            num_payments: 12 o 14 (para distribuir la retención mensual).
        """
        # Paso 1: Rendimiento neto del trabajo
        net_income = annual_gross - annual_ss_worker - _OTHER_WORK_EXPENSES
        net_income = max(net_income, 0.0)

        # Paso 2: Reducción por obtención de rendimientos del trabajo
        work_reduction = self._work_income_reduction(net_income)

        # Paso 3: Base liquidable
        taxable_base = max(net_income - work_reduction, 0.0)

        # Paso 4: Mínimo personal y familiar
        personal_minimum = self._personal_family_minimum(num_children, children_under_3)

        # Paso 5: Cuota sobre la renta
        tax_on_income = self._apply_scale(taxable_base)

        # Paso 6: Cuota sobre el mínimo
        tax_on_minimum = self._apply_scale(personal_minimum)

        # Paso 7: Retención
        annual_retention = max(tax_on_income - tax_on_minimum, 0.0)

        # Paso 8: Tipo de retención (%)
        retention_rate = (annual_retention / annual_gross * 100) if annual_gross > 0 else 0.0

        # Paso 9: Aplicar mínimo de retención
        is_temporal = contract_type in (
            "temporal", "temporal-produccion", "sustitucion",
        )
        min_rate = _MIN_RETENTION_TEMPORAL if is_temporal else _MIN_RETENTION_GENERAL
        retention_rate = max(retention_rate, min_rate)

        # Recalcular retención anual con el tipo ajustado
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
        )

    @staticmethod
    def _work_income_reduction(net_income: float) -> float:
        """Reducción por obtención de rendimientos del trabajo (art. 20 LIRPF 2025)."""
        if net_income <= 14_852.0:
            return 7_302.0
        if net_income <= 17_673.52:
            return 7_302.0 - 1.75 * (net_income - 14_852.0)
        return 2_364.34

    @staticmethod
    def _personal_family_minimum(num_children: int, children_under_3: int) -> float:
        """Mínimo personal y familiar."""
        total = _PERSONAL_MINIMUM
        for i in range(num_children):
            idx = min(i, len(_CHILD_MINIMUMS) - 1)
            total += _CHILD_MINIMUMS[idx]
        total += children_under_3 * _CHILD_UNDER_3_EXTRA
        return total

    @staticmethod
    def _apply_scale(amount: float) -> float:
        """Aplica la escala progresiva a un importe."""
        tax = 0.0
        prev_limit = 0.0
        for limit, rate in _BRACKETS:
            taxable_in_bracket = min(amount, limit) - prev_limit
            if taxable_in_bracket <= 0:
                break
            tax += taxable_in_bracket * rate
            prev_limit = limit
        return tax
