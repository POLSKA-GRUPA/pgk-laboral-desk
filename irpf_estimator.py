"""Estimación de retención IRPF — 2026.

Escalas separadas: estatal + autonómica (por CC.AA.).
CC.AA. soportadas: Madrid, Cataluña, Andalucía, C. Valenciana + genérica.

Incorpora:
- Umbrales de exención (Art. 81 RIRPF) — por debajo de ciertos brutos
  anuales según situación familiar NO se practica retención.
- Deducción por rendimientos del trabajo (RDL 5/2026, DA 61ª LIRPF)
  que elimina la tributación para perceptores del SMI 2026 (17.094 €/año)
  y la reduce progresivamente hasta ~20.000 €.
- Retención mínima 2% para contratos temporales / duración < 1 año
  (Art. 86.2 RIRPF), salvo que el trabajador esté exento.
- Reducción por rendimientos del trabajo (Art. 20 LIRPF, redacción
  RDL 4/2024): hasta 7.302 € para rentas netas ≤ 14.852 €, con
  reducción progresiva hasta 19.747,50 €.

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

# SMI 2026 — RD 126/2026: 1.221 €/mes × 14 pagas = 17.094 €/año
_SMI_ANNUAL_2026 = 17_094.0

# Deducción por rendimientos del trabajo para perceptores del SMI
# (RDL 5/2026, art. 28 — modifica DA 61ª LIRPF)
# Importe máximo: 591 € (neutraliza la cuota IRPF del SMI).
# Se aplica íntegra si bruto ≤ SMI, decrece linealmente hasta 0 en 20.000 €.
_SMI_DEDUCTION_MAX = 591.0
_SMI_DEDUCTION_UPPER = 20_000.0

# Umbrales de exención de retención (Art. 81 RIRPF, actualizados 2026).
# Si el bruto anual no supera estos importes, NO se practica retención.
# Claves: (num_children, has_spouse_low_income) → umbral €/año
# "has_spouse_low_income" = cónyuge con rentas < 1.500 €/año
_EXEMPTION_THRESHOLDS: dict[tuple[int, bool], float] = {
    # Situación C: soltero/a, viudo/a, divorciado/a, separado/a
    (0, False): 15_947.0,
    (1, False): 17_100.0,
    (2, False): 17_100.0,  # 2 o más hijos
    # Situación B: casado/a con cónyuge rentas < 1.500 €
    (0, True): 17_197.0,
    (1, True): 18_130.0,
    (2, True): 19_262.0,  # 2 o más hijos
}


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
        has_spouse_low_income: bool = False,
    ) -> IRPFResult:
        # ── 0. Umbral de exención (Art. 81 RIRPF) ──────────────────────
        # Si el bruto anual no supera el umbral según situación familiar,
        # NO se practica retención alguna (ni siquiera el 2% de temporal).
        exempt = self._is_exempt(annual_gross, num_children, has_spouse_low_income)

        region_key = region.lower().replace("ñ", "n").replace("í", "i").replace("á", "a")
        if region_key not in _REGIONAL_BRACKETS:
            region_key = "generica"

        if exempt:
            return IRPFResult(
                annual_gross=annual_gross,
                annual_ss_worker=annual_ss_worker,
                taxable_base=0.0,
                work_reduction=0.0,
                personal_family_minimum=0.0,
                tax_on_income=0.0,
                tax_on_minimum=0.0,
                annual_retention=0.0,
                retention_rate_pct=0.0,
                monthly_retention=0.0,
                region=region_key,
            )

        # ── 1. Rendimiento neto ─────────────────────────────────────────
        net_income = max(annual_gross - annual_ss_worker - _OTHER_WORK_EXPENSES, 0.0)

        # ── 2. Reducción rendimientos del trabajo (Art. 20 LIRPF) ──────
        work_reduction = self._work_income_reduction(net_income)

        # ── 3. Base liquidable ──────────────────────────────────────────
        taxable_base = max(net_income - work_reduction, 0.0)

        # ── 4. Mínimo personal y familiar ───────────────────────────────
        personal_minimum = self._personal_family_minimum(num_children, children_under_3)

        # ── 5. Cuotas: estatal + autonómica ─────────────────────────────
        tax_state = self._apply_scale(taxable_base, _STATE_BRACKETS)
        tax_region = self._apply_scale(taxable_base, _REGIONAL_BRACKETS[region_key])
        tax_on_income = tax_state + tax_region

        min_state = self._apply_scale(personal_minimum, _STATE_BRACKETS)
        min_region = self._apply_scale(personal_minimum, _REGIONAL_BRACKETS[region_key])
        tax_on_minimum = min_state + min_region

        # ── 6. Cuota previa de retención ────────────────────────────────
        annual_retention = max(tax_on_income - tax_on_minimum, 0.0)

        # ── 7. Deducción SMI (RDL 5/2026, DA 61ª LIRPF) ────────────────
        # Neutraliza la cuota del SMI; decrece linealmente SMI → 20.000 €.
        smi_deduction = self._smi_deduction(annual_gross)
        annual_retention = max(annual_retention - smi_deduction, 0.0)

        # ── 8. Tipo de retención ────────────────────────────────────────
        retention_rate = (annual_retention / annual_gross * 100) if annual_gross > 0 else 0.0

        # ── 9. Mínimo 2 % para contratos temporales (Art. 86.2 RIRPF) ──
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
    def _is_exempt(annual_gross: float, num_children: int, has_spouse_low_income: bool) -> bool:
        """Determina si el trabajador está exento de retención (Art. 81 RIRPF).

        Si el bruto anual no supera el umbral correspondiente a su
        situación familiar, no se practica retención.
        """
        children_key = min(num_children, 2)  # 2 = "2 o más"
        threshold = _EXEMPTION_THRESHOLDS.get(
            (children_key, has_spouse_low_income),
            _EXEMPTION_THRESHOLDS[(0, False)],  # default: soltero sin hijos
        )
        return annual_gross <= threshold

    @staticmethod
    def _smi_deduction(annual_gross: float) -> float:
        """Deducción por rendimientos del trabajo — perceptores SMI.

        RDL 5/2026 (art. 28), modifica DA 61ª LIRPF:
        - Hasta SMI (17.094 €): deducción íntegra de 591 €.
        - Entre SMI y 20.000 €: decrece linealmente hasta 0 €.
        - Más de 20.000 €: 0 €.
        """
        if annual_gross <= _SMI_ANNUAL_2026:
            return _SMI_DEDUCTION_MAX
        if annual_gross >= _SMI_DEDUCTION_UPPER:
            return 0.0
        # Reducción lineal
        ratio = (annual_gross - _SMI_ANNUAL_2026) / (_SMI_DEDUCTION_UPPER - _SMI_ANNUAL_2026)
        return round(_SMI_DEDUCTION_MAX * (1.0 - ratio), 2)

    @staticmethod
    def _work_income_reduction(net_income: float) -> float:
        """Reducción por rendimientos del trabajo (Art. 20 LIRPF, RDL 4/2024).

        a) Rendimiento neto <= 14.852: 7.302
        b) 14.852 < rend. neto <= 17.673,52: 7.302 - 1,75 * (rend. - 14.852)
        c) 17.673,52 < rend. neto <= 19.747,50: 2.364,34 - 1,14 * (rend. - 17.673,52)
        d) Mas de 19.747,50: 0 (no aplica reduccion)
        """
        if net_income <= 14_852.0:
            return 7_302.0
        if net_income <= 17_673.52:
            return max(7_302.0 - 1.75 * (net_income - 14_852.0), 0.0)
        if net_income <= 19_747.50:
            return max(2_364.34 - 1.14 * (net_income - 17_673.52), 0.0)
        return 0.0

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
