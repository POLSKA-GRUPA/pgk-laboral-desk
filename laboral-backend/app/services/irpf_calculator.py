"""Calculadora de IRPF 2026 — Retenciones sobre rendimientos del trabajo.

Referencias legales:
  - Ley 35/2006 (LIRPF): Arts. 19, 20, 57, 58, 59, 86
  - RD 439/2007 (RIRPF): Art. 80-93 (cálculo retenciones)
  - Orden HAC/2025 (tablas retención 2026)
  - RDL 4/2024 (reducción rendimientos trabajo Art. 20 LIRPF)
  - RDL 5/2026 (DA 61ª LIRPF — deducción SMI)

Usa Decimal en TODOS los cálculos monetarios.

NOTA: Tramos actualizados a 2026 para alinearse con IRPFEstimator.
"""

from decimal import ROUND_HALF_UP, Decimal

# ---------------------------------------------------------------------------
# Constantes IRPF 2026
# ---------------------------------------------------------------------------

TWO_PLACES = Decimal("0.01")

# Tramos IRPF 2026 (estatal + autonómico genérica combinados)
# Alineados con IRPFEstimator: estatal 9.5%+12%+15%+18.5%+22.5%+24.5%
# + autonómica genérica (= estatal) = tipos sumados.
IRPF_TRAMOS_2026 = (
    (Decimal("0"), Decimal("12450"), Decimal("0.19")),
    (Decimal("12450"), Decimal("20200"), Decimal("0.24")),
    (Decimal("20200"), Decimal("35200"), Decimal("0.30")),
    (Decimal("35200"), Decimal("60000"), Decimal("0.37")),
    (Decimal("60000"), Decimal("300000"), Decimal("0.45")),
    (Decimal("300000"), None, Decimal("0.49")),
)

# Mínimo personal — Art.57 LIRPF
MINIMO_PERSONAL = Decimal("5550")

# Mínimo por descendientes — Art.58 LIRPF
MINIMO_DESCENDIENTES = (
    Decimal("2400"),  # hijo 1
    Decimal("2700"),  # hijo 2
    Decimal("4000"),  # hijo 3
    Decimal("4500"),  # hijo 4+
)

# Mínimo por ascendientes — Art.59 LIRPF
MINIMO_ASCENDIENTE = Decimal("1150")
MINIMO_ASCENDIENTE_DISCAPACIDAD = Decimal("2550")

# Reducción por rendimientos del trabajo — Art.20 LIRPF (RDL 4/2024)
# Tramos actualizados a 2026:
#   a) Rend. neto <= 14.852: 7.302 €
#   b) 14.852 < rend <= 17.673,52: 7.302 - 1,75 * (rend - 14.852)
#   c) 17.673,52 < rend <= 19.747,50: 2.364,34 - 1,14 * (rend - 17.673,52)
#   d) > 19.747,50: 0
REDUCCION_TRABAJO_TRAMO_1 = Decimal("14852")
REDUCCION_TRABAJO_TRAMO_2 = Decimal("17673.52")
REDUCCION_TRABAJO_TRAMO_3 = Decimal("19747.50")
REDUCCION_TRABAJO_MAX = Decimal("7302")
REDUCCION_TRABAJO_COEF_1 = Decimal("1.75")
REDUCCION_TRABAJO_COEF_2 = Decimal("1.14")
REDUCCION_TRABAJO_BASE_2 = Decimal("2364.34")

# Umbral de exención IRPF (Art. 81 RIRPF, actualizado 2026)
EXENCION_LIMITE = Decimal("15947")

# Retención mínima — Art.80.3 RIRPF
RETENCION_MINIMA = Decimal("0.02")
RETENCION_MINIMA_LIMITE = Decimal("12000")

# Situaciones familiares
SITUACIONES_FAMILIARES = (
    "soltero",
    "casado_un_perceptor",
    "casado_dos_perceptores",
    "monoparental",
    "familia_numerosa_general",
    "familia_numera_especial",
)

# Coeficientes reductores por situación familiar (Art.86 RIRPF)
COEFICIENTE_FAMILIAR = {
    "soltero": Decimal("1.00"),
    "casado_un_perceptor": Decimal("1.00"),
    "casado_dos_perceptores": Decimal("1.05"),
    "monoparental": Decimal("0.95"),
    "familia_numerosa_general": Decimal("0.90"),
    "familia_numera_especial": Decimal("0.85"),
}


def _round2(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _round4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class IRPFCalculator:
    """Calculadora de retenciones IRPF 2026 sobre nóminas."""

    # ------------------------------------------------------------------ #
    # API principal
    # ------------------------------------------------------------------ #

    def calcular_retencion_mensual(
        self,
        salario_bruto_mensual: float,
        num_pagas: int = 14,
        situacion_familiar: str = "soltero",
        num_hijos: int = 0,
        comunidad_autonoma: str = "madrid",
        num_ascendientes: int = 0,
        discapacidad_pct: int = 0,
        contrato_temporal: bool = False,
    ) -> dict:
        """Calcula la retención IRPF mensual sobre nómina.

        Returns:
            dict con tipo_retencion (%), retencion_mensual (€), desgloses.
        """
        bruto = Decimal(str(salario_bruto_mensual))
        pagas = Decimal(str(num_pagas))
        bruto_anual = bruto * pagas

        # Exención rentas < 14.000 €/año
        if bruto_anual <= EXENCION_LIMITE:
            return self._resultado_exento(bruto_anual, bruto, pagas)

        # 1. Cuotas SS trabajador 2026 (6.50% indefinido, 6.55% temporal)
        tasa_ss = Decimal("0.0655") if contrato_temporal else Decimal("0.0650")
        ss_anual = _round2(bruto * tasa_ss) * pagas

        # 2. Rendimiento neto del trabajo
        rendimiento_neto = bruto_anual - ss_anual

        # 3. Reducción por rendimientos del trabajo (Art.20 LIRPF)
        reduccion = self._reduccion_trabajo(rendimiento_neto)

        # 4. Base liquidable = rendimiento neto - reducción
        rendimiento_neto_reducido = max(Decimal("0"), rendimiento_neto - reduccion)

        # 5. Mínimo personal y familiar
        minimo_total = self._calcular_minimo_total(
            situacion_familiar, num_hijos, num_ascendientes, discapacidad_pct
        )

        # 6. Base liquidable ajustada
        base_liquidable = max(Decimal("0"), rendimiento_neto_reducido - minimo_total)

        # 7. Cuota íntegra (tramos progresivos)
        cuota, desglose_tramos = self._cuota_por_tramos(base_liquidable)

        # 8. Tipo de retención
        tipo = self._calcular_tipo_retencion(cuota, bruto_anual, situacion_familiar)

        # 9. Retención mensual
        retencion_anual = _round2(bruto_anual * tipo / Decimal("100"))
        retencion_mensual = _round2(retencion_anual / pagas)

        return {
            "salario_bruto_anual": float(_round2(bruto_anual)),
            "ss_trabajador_anual": float(ss_anual),
            "rendimiento_neto": float(_round2(rendimiento_neto)),
            "reduccion_art20": float(_round2(reduccion)),
            "rendimiento_neto_reducido": float(_round2(rendimiento_neto_reducido)),
            "minimo_personal_familiar": float(_round2(minimo_total)),
            "base_liquidable": float(_round2(base_liquidable)),
            "cuota_integra": float(_round2(cuota)),
            "tipo_retencion_pct": float(_round4(tipo)),
            "retencion_anual": float(retencion_anual),
            "retencion_mensual": float(retencion_mensual),
            "desglose_tramos": desglose_tramos,
            "situacion_familiar": situacion_familiar,
            "comunidad_autonoma": comunidad_autonoma,
            "exento": False,
        }

    def calcular_neto(
        self,
        salario_bruto_mensual: float,
        num_pagas: int = 14,
        situacion_familiar: str = "soltero",
        num_hijos: int = 0,
        comunidad_autonoma: str = "madrid",
        contrato_temporal: bool = False,
    ) -> dict:
        """Calcula nómina neta a partir del bruto mensual."""
        irpf = self.calcular_retencion_mensual(
            salario_bruto_mensual,
            num_pagas,
            situacion_familiar,
            num_hijos,
            comunidad_autonoma,
            contrato_temporal=contrato_temporal,
        )
        bruto = Decimal(str(salario_bruto_mensual))
        tasa_ss = Decimal("0.0655") if contrato_temporal else Decimal("0.0650")
        ss_mensual = _round2(bruto * tasa_ss)
        irpf_mensual = Decimal(str(irpf["retencion_mensual"]))
        total_deducciones = _round2(ss_mensual + irpf_mensual)
        neto = _round2(bruto - total_deducciones)

        return {
            "salario_bruto_mensual": float(_round2(bruto)),
            "ss_trabajador_mensual": float(ss_mensual),
            "irpf_mensual": float(irpf_mensual),
            "total_deducciones": float(total_deducciones),
            "salario_neto_mensual": float(neto),
            "salario_neto_anual": float(_round2(neto * num_pagas)),
            "tipo_irpf": irpf["tipo_retencion_pct"],
            "tipo_ss": float(_round4(tasa_ss * 100)),
        }

    # ------------------------------------------------------------------ #
    # Componentes internos
    # ------------------------------------------------------------------ #

    @staticmethod
    def _reduccion_trabajo(rendimiento_neto: Decimal) -> Decimal:
        """Reducción por rendimientos del trabajo — Art.20 LIRPF (RDL 4/2024).

        a) Rend. neto <= 14.852: 7.302 €
        b) 14.852 < rend <= 17.673,52: 7.302 - 1,75 * (rend - 14.852)
        c) 17.673,52 < rend <= 19.747,50: 2.364,34 - 1,14 * (rend - 17.673,52)
        d) > 19.747,50: 0
        """
        if rendimiento_neto <= Decimal("0"):
            return Decimal("0")
        if rendimiento_neto <= REDUCCION_TRABAJO_TRAMO_1:
            return min(REDUCCION_TRABAJO_MAX, rendimiento_neto)
        if rendimiento_neto <= REDUCCION_TRABAJO_TRAMO_2:
            exceso = rendimiento_neto - REDUCCION_TRABAJO_TRAMO_1
            reduccion = REDUCCION_TRABAJO_MAX - _round2(exceso * REDUCCION_TRABAJO_COEF_1)
            return max(Decimal("0"), reduccion)
        if rendimiento_neto <= REDUCCION_TRABAJO_TRAMO_3:
            exceso = rendimiento_neto - REDUCCION_TRABAJO_TRAMO_2
            reduccion = REDUCCION_TRABAJO_BASE_2 - _round2(exceso * REDUCCION_TRABAJO_COEF_2)
            return max(Decimal("0"), reduccion)
        return Decimal("0")

    @staticmethod
    def _calcular_minimo_total(
        situacion: str,
        num_hijos: int,
        num_ascendientes: int,
        discapacidad_pct: int = 0,
    ) -> Decimal:
        """Suma mínimo personal + descendientes + ascendientes."""
        total = MINIMO_PERSONAL

        # Descendientes
        for i in range(min(num_hijos, 10)):
            if i < len(MINIMO_DESCENDIENTES):
                total += MINIMO_DESCENDIENTES[i]
            else:
                total += MINIMO_DESCENDIENTES[-1]

        # Ascendientes
        for _ in range(min(num_ascendientes, 4)):
            if discapacidad_pct >= 33:
                total += MINIMO_ASCENDIENTE_DISCAPACIDAD
            else:
                total += MINIMO_ASCENDIENTE

        return total

    @staticmethod
    def _cuota_por_tramos(base: Decimal) -> tuple[Decimal, list[dict]]:
        """Aplica tramos progresivos IRPF. Devuelve (cuota, desglose)."""
        cuota = Decimal("0")
        desglose = []
        for minimo, maximo, tipo in IRPF_TRAMOS_2026:
            if base <= minimo:
                break
            limite = maximo if maximo is not None else base
            base_tramo = min(base, limite) - minimo
            cuota_tramo = _round2(base_tramo * tipo)
            cuota += cuota_tramo
            desglose.append(
                {
                    "desde": float(minimo),
                    "hasta": float(limite) if maximo else "∞",
                    "tipo": float(tipo * 100),
                    "base_tramo": float(_round2(base_tramo)),
                    "cuota_tramo": float(cuota_tramo),
                }
            )
        return cuota, desglose

    def _calcular_tipo_retencion(
        self, cuota: Decimal, bruto_anual: Decimal, situacion: str
    ) -> Decimal:
        """Tipo de retencion = cuota / bruto x 100, con minimos legales."""
        if bruto_anual <= Decimal("0"):
            return Decimal("0")
        tipo = (cuota / bruto_anual) * Decimal("100")
        # Retención mínima para rentas < 12.000
        if bruto_anual < RETENCION_MINIMA_LIMITE and tipo < RETENCION_MINIMA * 100:
            tipo = RETENCION_MINIMA * 100
        # Coeficiente por situación familiar
        coef = COEFICIENTE_FAMILIAR.get(situacion, Decimal("1.00"))
        tipo = tipo * coef
        return tipo

    @staticmethod
    def _resultado_exento(bruto_anual: Decimal, bruto_mensual: Decimal, pagas: Decimal) -> dict:
        return {
            "salario_bruto_anual": float(_round2(bruto_anual)),
            "ss_trabajador_anual": 0.0,
            "rendimiento_neto": float(_round2(bruto_anual)),
            "reduccion_art20": 0.0,
            "rendimiento_neto_reducido": 0.0,
            "minimo_personal_familiar": float(MINIMO_PERSONAL),
            "base_liquidable": 0.0,
            "cuota_integra": 0.0,
            "tipo_retencion_pct": 0.0,
            "retencion_anual": 0.0,
            "retencion_mensual": 0.0,
            "desglose_tramos": [],
            "situacion_familiar": "soltero",
            "comunidad_autonoma": "madrid",
            "exento": True,
        }
