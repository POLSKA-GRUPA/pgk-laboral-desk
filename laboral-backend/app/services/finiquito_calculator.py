"""Calculadora de finiquito y liquidación — extinción contrato laboral.

Referencias: ET Arts. 49, 52, 56, 56.bis | LIRPF Art.7.e | RD 2104/1998
Usa Decimal en todos los cálculos."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")

# Indemnización por tipo de extinción (días por año trabajado)
DIAS_POR_ANO = {
    "improcedente": 33,
    "objetivo": 20,
    "objetivo_ere": 20,
    "despido_colectivo": 20,
    "voluntario": 0,
    "mutuo_acuerdo": 0,
    "fin_contrato_temporal": 12,
    "fin_contrato_formacion": 0,
    "fin_contrato_practicas": 0,
    "dimision": 0,
    "jubilacion": 0,
    "muerte": 0,
    "fuerza_mayor": 20,
    "incapacidad_permanente": 12,
}

TOPE_MESES = {
    "improcedente": 24,
    "objetivo": 12,
    "objetivo_ere": 12,
    "despido_colectivo": 12,
    "voluntario": None,
    "mutuo_acuerdo": None,
    "fin_contrato_temporal": None,
    "dimision": None,
    "jubilacion": None,
    "muerte": None,
    "fuerza_mayor": 12,
    "incapacidad_permanente": None,
}

# Indemnización exenta de IRPF e IS — Art.7.e LIRPF
EXENCION_INDEMNIZACION_LIMITE = Decimal("180000")

# Contratos anteriores a 12/02/2012 (reforma laboral): 45 días/año, tope 42 meses
FECHA_REFORMA_LABORAL = date(2012, 2, 12)
DIAS_ANTERIOR_REFORMA = 45
TOPE_ANTERIOR_REFORMA = 42


def _r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class FiniquitoCalculator:
    """Calculadora de finiquito y liquidación por extinción de contrato."""

    def calcular(
        self,
        salario_bruto_mensual: float,
        fecha_inicio: date,
        fecha_fin: date,
        tipo_extincion: str = "improcedente",
        dias_vacaciones_pendientes: int = 0,
        num_pagas: int = 14,
        pagas_extras_prorrateadas: bool = False,
    ) -> dict:
        """Cálculo completo de finiquito + liquidación.

        Returns:
            dict con desglose completo: haberes, indemnización, IRPF, neto.
        """
        bruto_mensual = Decimal(str(salario_bruto_mensual))
        bruto_diario = _r2(bruto_mensual / Decimal("30"))
        bruto_anual = bruto_mensual * num_pagas

        # Antigüedad
        antiguedad_dias = (fecha_fin - fecha_inicio).days
        antiguedad_anos = Decimal(str(antiguedad_dias)) / Decimal("365.25")

        # === PARTE PROPORCIONAL HABERES ===
        dias_ultimo_mes = fecha_fin.day
        salario_dias = _r2(bruto_diario * dias_ultimo_mes)

        # === PARTE PROPORCIONAL PAGAS EXTRAS ===
        if num_pagas > 12 and not pagas_extras_prorrateadas:
            pagas_extra = num_pagas - 12
            importe_paga = bruto_mensual
            meses_transcurridos = Decimal(str(fecha_fin.month))
            parte_proporcional_pagas = _r2(
                (importe_paga * pagas_extra * meses_transcurridos) / Decimal("12")
            )
        elif pagas_extras_prorrateadas:
            parte_proporcional_pagas = Decimal("0")
        else:
            parte_proporcional_pagas = Decimal("0")

        # === VACACIONES NO DISFRUTADAS ===
        vacaciones_valor = _r2(bruto_diario * dias_vacaciones_pendientes)

        # === SUBTOTAL LIQUIDACIÓN (haberes) ===
        subtotal_liquidacion = _r2(salario_dias + parte_proporcional_pagas + vacaciones_valor)

        # === INDEMNIZACIÓN ===
        indemnizacion = self._calcular_indemnizacion(
            bruto_diario, bruto_mensual, fecha_inicio, fecha_fin, tipo_extincion
        )

        # === TOTAL BRUTO ===
        total_bruto = _r2(subtotal_liquidacion + Decimal(str(indemnizacion["importe"])))

        # === IRPF ===
        # La indemnización legalmente reconocida está exenta (Art.7.e LIRPF)
        # Solo tributa la liquidación (haberes + vacaciones)
        base_irpf = subtotal_liquidacion
        irpf_haberes = self._estimar_irpf_finiquito(base_irpf, bruto_anual)

        # === SS ===
        # Las vacaciones no disfrutadas SIEMPRE cotizan a SS
        # La indemnización NO cotiza (hasta límite legal)
        base_ss = _r2(salario_dias + vacaciones_valor + parte_proporcional_pagas)
        ss_trabajador = _r2(base_ss * Decimal("0.0635"))

        # === TOTAL NETO ===
        total_deducciones = _r2(irpf_haberes + ss_trabajador)
        total_neto = _r2(total_bruto - total_deducciones)

        return {
            "dias_ultimo_mes": dias_ultimo_mes,
            "salario_dias_trabajados": float(salario_dias),
            "parte_proporcional_pagas": float(parte_proporcional_pagas),
            "vacaciones_pendientes_valor": float(vacaciones_valor),
            "subtotal_liquidacion": float(subtotal_liquidacion),
            "indemnizacion": indemnizacion,
            "total_bruto": float(total_bruto),
            "base_irpf": float(base_irpf),
            "irpf_haberes": float(irpf_haberes),
            "base_ss": float(base_ss),
            "ss_trabajador": float(ss_trabajador),
            "total_deducciones": float(total_deducciones),
            "total_neto": float(total_neto),
            "antiguedad_anos": float(_r2(antiguedad_anos)),
            "antiguedad_dias": antiguedad_dias,
            "tipo_extincion": tipo_extincion,
            "nota_indemnizacion_exenta": (
                f"Indemnización exenta IRPF/IS hasta {EXENCION_INDEMNIZACION_LIMITE}€ "
                f"(Art.7.e LIRPF)"
            ),
            "nota_vacaciones_cotizan": "Vacaciones no disfrutadas SIEMPRE cotizan a SS y tributan IRPF",
        }

    def _calcular_indemnizacion(
        self,
        bruto_diario: Decimal,
        bruto_mensual: Decimal,
        fecha_inicio: date,
        fecha_fin: date,
        tipo: str,
    ) -> dict:
        dias_por_ano = DIAS_POR_ANO.get(tipo, 0)
        tope_meses = TOPE_MESES.get(tipo)

        if dias_por_ano == 0:
            return {
                "importe": 0.0,
                "dias_por_ano": dias_por_ano,
                "tope_meses": tope_meses,
                "tipo_calculo": "sin_indemnizacion",
                "exenta_irpf": True,
            }

        antiguedad_dias = (fecha_fin - fecha_inicio).days
        antiguedad_anos = Decimal(str(antiguedad_dias)) / Decimal("365.25")

        # Reforma laboral: calcular por tramos si contrato anterior a 12/02/2012
        if fecha_inicio < FECHA_REFORMA_LABORAL and tipo in ("improcedente",):
            return self._indemnizacion_tramos_reforma(
                bruto_diario, bruto_mensual, fecha_inicio, fecha_fin
            )

        indemnizacion = _r2(bruto_diario * dias_por_ano * antiguedad_anos)

        if tope_meses:
            tope = _r2(bruto_mensual * tope_meses)
            indemnizacion_tope = min(indemnizacion, tope)
            tope_aplicado = indemnizacion > tope
        else:
            indemnizacion_tope = indemnizacion
            tope_aplicado = False

        exenta = indemnizacion_tope <= EXENCION_INDEMNIZACION_LIMITE

        return {
            "importe": float(indemnizacion_tope),
            "dias_por_ano": dias_por_ano,
            "anos_antiguedad": float(_r2(antiguedad_anos)),
            "tope_meses": tope_meses,
            "tope_aplicado": tope_aplicado,
            "tipo_calculo": "estandar",
            "exenta_irpf": exenta,
        }

    @staticmethod
    def _indemnizacion_tramos_reforma(
        bruto_diario: Decimal,
        bruto_mensual: Decimal,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> dict:
        """Contratos anteriores a reforma: 45 días/año (hasta 12/02/2012) + 33 días/año (desde)."""
        fecha_corte = FECHA_REFORMA_LABORAL
        dias_antes = max(0, (fecha_corte - fecha_inicio).days)
        dias_despues = max(0, (fecha_fin - fecha_corte).days)
        anos_antes = Decimal(str(dias_antes)) / Decimal("365.25")
        anos_despues = Decimal(str(dias_despues)) / Decimal("365.25")

        ind_antes = _r2(bruto_diario * DIAS_ANTERIOR_REFORMA * anos_antes)
        ind_despues = _r2(bruto_diario * 33 * anos_despues)
        total = _r2(ind_antes + ind_despues)

        tope_42 = _r2(bruto_mensual * TOPE_ANTERIOR_REFORMA)
        tope_24 = _r2(bruto_mensual * 24)
        tope = min(tope_42, tope_24)
        total = min(total, tope)

        return {
            "importe": float(total),
            "dias_por_ano": 45,
            "anos_antiguedad": float(
                _r2(Decimal(str(dias_antes + dias_despues)) / Decimal("365.25"))
            ),
            "tope_meses": min(TOPE_ANTERIOR_REFORMA, 24),
            "tope_aplicado": total >= tope,
            "tipo_calculo": "tramos_reforma_2012",
            "tramo_antes_2012": {"dias_por_ano": 45, "importe": float(ind_antes)},
            "tramo_despues_2012": {"dias_por_ano": 33, "importe": float(ind_despues)},
            "exenta_irpf": total <= float(EXENCION_INDEMNIZACION_LIMITE),
        }

    @staticmethod
    def _estimar_irpf_finiquito(base_haberes: Decimal, bruto_anual: Decimal) -> Decimal:
        # Estimación conservadora: tipo medio sobre nóminas anteriores
        if bruto_anual <= Decimal("14000"):
            return Decimal("0")
        tipo_estimado = min(Decimal("0.35"), max(Decimal("0.02"), bruto_anual * Decimal("0.00002")))
        return _r2(base_haberes * tipo_estimado)
