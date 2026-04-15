"""Calculadora de cuotas RETA 2025 — Régimen Especial de Trabajadores Autónomos.

Sistema de cotización por ingresos reales (vigente desde 01/01/2023).
15 tramos + tarifa plana + MEI.
Referencias: LGSS DA 15ª | Orden ISM/31/2026 | Ley 12/2023"""

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")

# Tipo de cotización RETA 2025: CC 28.30% + MEI 0.58% = 28.88%
TIPO_CC = Decimal("0.2830")
TIPO_MEI_2025 = Decimal("0.0058")
TIPO_MEI_2026 = Decimal("0.0067")
TIPO_TOTAL_2025 = TIPO_CC + TIPO_MEI_2025  # 28.88%
TIPO_TOTAL_2026 = TIPO_CC + TIPO_MEI_2026  # 28.97%

# 15 tramos RETA 2025: (nombre, ingresos_desde, ingresos_hasta, base_min, base_max)
TRAMOS_RETA_2025 = (
    ("T1_tarifa_plana", Decimal("0"), Decimal("670"), Decimal("200"), Decimal("670")),
    ("T2", Decimal("0"), Decimal("670"), Decimal("735.29"), Decimal("816.98")),
    ("T3", Decimal("670"), Decimal("900"), Decimal("816.98"), Decimal("900")),
    ("T4", Decimal("900"), Decimal("1166.70"), Decimal("872.55"), Decimal("1166.70")),
    ("T5", Decimal("1166.70"), Decimal("1300"), Decimal("950.98"), Decimal("1300")),
    ("T6", Decimal("1300"), Decimal("1500"), Decimal("960.78"), Decimal("1500")),
    ("T7", Decimal("1500"), Decimal("1700"), Decimal("960.78"), Decimal("1700")),
    ("T8", Decimal("1700"), Decimal("1850"), Decimal("1013.07"), Decimal("1850")),
    ("T9", Decimal("1850"), Decimal("2030"), Decimal("1029.41"), Decimal("2030")),
    ("T10", Decimal("2030"), Decimal("2330"), Decimal("1045.75"), Decimal("2330")),
    ("T11", Decimal("2330"), Decimal("2760"), Decimal("1078.43"), Decimal("2760")),
    ("T12", Decimal("2760"), Decimal("3190"), Decimal("1111.11"), Decimal("3190")),
    ("T13", Decimal("3190"), Decimal("3620"), Decimal("1176.47"), Decimal("3620")),
    ("T14", Decimal("3620"), Decimal("4050"), Decimal("1241.76"), Decimal("4050")),
    ("T15", Decimal("4050"), None, Decimal("1307.05"), Decimal("4495.50")),
)

TARIFA_PLANA_NUEVO = Decimal("80")
TARIFA_PLANA_MESES = 12
TARIFA_PLANA_REQUISITO_ANOS = 2  # No haber sido autónomo en los últimos 2 años

BASE_MAXIMA_2025 = Decimal("4495.50")

# Prestación cese de actividad
CESE_ACTIVIDAD_MIN_MESES = 12
CESE_ACTIVIDAD_COBERTURA_PCT = Decimal("0.70")


def _r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class RETACalculator:
    """Calculadora de cuotas RETA por tramos de ingresos."""

    def calcular_cuota(
        self,
        ingresos_brutos_mensuales: float,
        gastos_deducibles_mensuales: float = 0,
        base_elegida: float | None = None,
        es_nuevo_autonomo: bool = False,
        meses_alta: int = 0,
        year: int = 2025,
    ) -> dict:
        ingresos_netos = Decimal(str(ingresos_brutos_mensuales)) - Decimal(
            str(gastos_deducibles_mensuales)
        )

        # Ingresos netos <= 0 → no hay actividad económica real
        if ingresos_netos <= Decimal("0") and not es_nuevo_autonomo:
            return {
                "ingresos_brutos_mensuales": float(_r2(Decimal(str(ingresos_brutos_mensuales)))),
                "gastos_deducibles_mensuales": float(_r2(Decimal(str(gastos_deducibles_mensuales)))),
                "ingresos_netos_mensuales": float(_r2(ingresos_netos)),
                "tramo": "sin_actividad",
                "base_cotizacion_mensual": 0.0,
                "base_minima_tramo": 0.0,
                "base_maxima_tramo": 0.0,
                "tipo_cotizacion_pct": 0.0,
                "cuota_mensual": 0.0,
                "cuota_anual": 0.0,
                "pct_cuota_sobre_ingresos": 0.0,
                "desglose": {
                    "contingencias_comunes_pct": 0.0,
                    "cc_mensual": 0.0,
                    "mei_pct": 0.0,
                    "mei_mensual": 0.0,
                },
                "es_tarifa_plana": False,
                "year": year,
                "nota": "Con ingresos netos ≤ 0 no existe obligación de cotización RETA.",
            }

        # Tarifa plana
        if es_nuevo_autonomo and meses_alta <= TARIFA_PLANA_MESES:
            return self._resultado_tarifa_plana(ingresos_netos, year)

        if ingresos_netos <= Decimal("0"):
            ingresos_netos = Decimal("1")

        tramo = self._encontrar_tramo(ingresos_netos)
        nombre, _desde, _hasta, base_min, base_max = tramo

        # Base de cotización
        if base_elegida is not None:
            base = Decimal(str(base_elegida))
            base = max(base_min, min(base, base_max))
        else:
            base = base_min

        tipo = TIPO_TOTAL_2025 if year == 2025 else TIPO_TOTAL_2026
        cuota = _r2(base * tipo)
        cuota_anual = _r2(cuota * 12)
        pct_sobre_ingresos = _r2(cuota / max(ingresos_netos, Decimal("1")) * 100)

        return {
            "ingresos_brutos_mensuales": float(_r2(Decimal(str(ingresos_brutos_mensuales)))),
            "gastos_deducibles_mensuales": float(_r2(Decimal(str(gastos_deducibles_mensuales)))),
            "ingresos_netos_mensuales": float(_r2(ingresos_netos)),
            "tramo": nombre,
            "base_cotizacion_mensual": float(base),
            "base_minima_tramo": float(base_min),
            "base_maxima_tramo": float(base_max),
            "tipo_cotizacion_pct": float(_r2(tipo * 100)),
            "cuota_mensual": float(cuota),
            "cuota_anual": float(cuota_anual),
            "pct_cuota_sobre_ingresos": float(pct_sobre_ingresos),
            "desglose": {
                "contingencias_comunes_pct": float(_r2(TIPO_CC * 100)),
                "cc_mensual": float(_r2(base * TIPO_CC)),
                "mei_pct": float(_r2((TIPO_MEI_2025 if year == 2025 else TIPO_MEI_2026) * 100)),
                "mei_mensual": float(
                    _r2(base * (TIPO_MEI_2025 if year == 2025 else TIPO_MEI_2026))
                ),
            },
            "es_tarifa_plana": False,
            "year": year,
        }

    def comparar_con_asalariado(
        self,
        ingresos_brutos_mensuales: float,
        gastos_deducibles_mensuales: float = 0,
    ) -> dict:
        """Compara cuotas autónomo vs asalariado equivalente.

        Porcentajes 2026 (Orden ISM/31/2026):
        - Trabajador: 4.70% CC + 1.55% desempleo + 0.10% FP + 0.15% MEI = 6.50%
        - Empresa: 23.60% CC + 5.50% desempleo + 0.60% FP + 0.20% FOGASA + 0.75% MEI + 1.50% AT = 32.15%
        """
        aut = self.calcular_cuota(ingresos_brutos_mensuales, gastos_deducibles_mensuales)
        bruto = Decimal(str(ingresos_brutos_mensuales))

        # Porcentajes SS asalariado 2026
        pct_trabajador = Decimal("0.0650")  # 6.50% total trabajador
        pct_empresa = Decimal("0.3215")     # 32.15% total empresa

        ss_asalariado = _r2(bruto * pct_trabajador)
        ss_empresa_asal = _r2(bruto * pct_empresa)

        return {
            "autonomo": {
                "cuota_ss_mensual": aut["cuota_mensual"],
                "cuota_ss_anual": aut["cuota_anual"],
                "pct_sobre_ingresos": aut["pct_cuota_sobre_ingresos"],
            },
            "asalariado": {
                "ss_trabajador_mensual": float(ss_asalariado),
                "ss_empresa_mensual": float(ss_empresa_asal),
                "total_ss_mensual": float(_r2(ss_asalariado + ss_empresa_asal)),
                "pct_trabajador_sobre_bruto": float(_r2(pct_trabajador * 100)),
                "pct_total_sobre_bruto": float(
                    _r2(pct_empresa * 100 + pct_trabajador * 100)
                ),
            },
            "diferencia": {
                "autonomo_paga_mas_mensual": float(
                    _r2(Decimal(str(aut["cuota_mensual"])) - ss_asalariado)
                ),
                "nota": "Autónomo paga íntegro; asalariado solo 6.50% (empresa paga 32.15%)",
            },
        }

    @staticmethod
    def _encontrar_tramo(ingresos: Decimal) -> tuple:
        for tramo in TRAMOS_RETA_2025:
            nombre, desde, hasta, _bmin, _bmax = tramo
            if nombre == "T1_tarifa_plana":
                continue
            if hasta is None:
                if ingresos >= desde:
                    return tramo
            elif desde <= ingresos < hasta:
                return tramo
        return TRAMOS_RETA_2025[1]

    @staticmethod
    def _resultado_tarifa_plana(ingresos: Decimal, year: int) -> dict:
        tipo = TIPO_TOTAL_2025 if year == 2025 else TIPO_TOTAL_2026
        base = _r2(TARIFA_PLANA_NUEVO / tipo)
        return {
            "ingresos_brutos_mensuales": 0.0,
            "gastos_deducibles_mensuales": 0.0,
            "ingresos_netos_mensuales": float(_r2(ingresos)),
            "tramo": "T1_tarifa_plana",
            "base_cotizacion_mensual": float(base),
            "base_minima_tramo": float(base),
            "base_maxima_tramo": float(base),
            "tipo_cotizacion_pct": float(_r2(tipo * 100)),
            "cuota_mensual": float(TARIFA_PLANA_NUEVO),
            "cuota_anual": float(TARIFA_PLANA_NUEVO * 12),
            "pct_cuota_sobre_ingresos": float(
                _r2(TARIFA_PLANA_NUEVO / max(ingresos, Decimal("1")) * 100)
            ),
            "desglose": {
                "contingencias_comunes_pct": float(_r2(TIPO_CC * 100)),
                "cc_mensual": float(_r2(base * TIPO_CC)),
                "mei_pct": float(_r2((TIPO_MEI_2025 if year == 2025 else TIPO_MEI_2026) * 100)),
                "mei_mensual": float(
                    _r2(base * (TIPO_MEI_2025 if year == 2025 else TIPO_MEI_2026))
                ),
            },
            "es_tarifa_plana": True,
            "meses_tarifa_plana_restantes": TARIFA_PLANA_MESES,
            "year": year,
        }
