"""Orquestador de nómina — bruto → neto + coste empresa.

Usa IRPFCalculator + SSCalculator para cálculo completo de nómina española.
Layout compatible con modelo oficial Orden ESS/2098/2014."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.services.irpf_calculator import IRPFCalculator
from app.services.ss_calculator import SSCalculator

TWO_PLACES = Decimal("0.01")


def _r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class NominaCalculator:
    """Orquestador de cálculo de nómina mensual."""

    def __init__(self, ss_config_path: str | None = None):
        self.irpf = IRPFCalculator()
        self.ss = SSCalculator(config_path=ss_config_path) if ss_config_path else None

    def calcular_nomina(
        self,
        salario_bruto_mensual: float,
        num_pagas: int = 14,
        situacion_familiar: str = "soltero",
        num_hijos: int = 0,
        comunidad_autonoma: str = "madrid",
        tipo_contrato: str = "indefinido",
        cnae: str = "",
        plus_transporte_mensual: float = 0,
        plus_comida_mensual: float = 0,
        horas_extras_mensual: float = 0,
        complemento_productividad: float = 0,
        antiguedad_anos: int = 0,
        categoria_profesional: str = "",
    ) -> dict:
        bruto = Decimal(str(salario_bruto_mensual))
        if bruto <= 0:
            raise ValueError("El salario bruto mensual debe ser mayor que 0.")
        transporte = Decimal(str(plus_transporte_mensual))
        comida = Decimal(str(plus_comida_mensual))
        he = Decimal(str(horas_extras_mensual))
        productividad = Decimal(str(complemento_productividad))

        # === DEVENGOS ===
        devengos_salariales = bruto + productividad + he
        devengos_no_salariales_exentos = transporte + comida
        total_devengado = _r2(devengos_salariales + devengos_no_salariales_exentos)

        # === BASE COTIZACIÓN SS ===
        # Si tenemos SSCalculator, delegar topes por grupo; si no, usar topes genéricos
        grupo_ss = ""
        if self.ss:
            grupo_ss = self.ss._resolve_grupo(categoria_profesional)
        base_cotizacion = self._calcular_base(devengos_salariales, transporte, comida, grupo_ss)

        # === SS TRABAJADOR ===
        ss_trab = self._ss_trabajador(base_cotizacion, tipo_contrato, he)

        # === IRPF ===
        irpf_result = self.irpf.calcular_retencion_mensual(
            float(devengos_salariales),
            num_pagas,
            situacion_familiar,
            num_hijos,
            comunidad_autonoma,
            contrato_temporal=(tipo_contrato in ("temporal", "formacion", "practicas")),
        )
        irpf_mensual = Decimal(str(irpf_result["retencion_mensual"]))
        tipo_irpf = Decimal(str(irpf_result["tipo_retencion_pct"]))

        # === DEDUCCIONES ===
        total_ss_trab = Decimal(str(ss_trab["total_ss_trabajador"]))
        total_deducciones = _r2(total_ss_trab + irpf_mensual)

        # === NETO ===
        neto_mensual = _r2(total_devengado - total_deducciones)

        # === SS EMPRESA + COSTE ===
        ss_emp = self._ss_empresa(base_cotizacion, tipo_contrato, cnae, he, categoria_profesional)
        total_ss_emp = Decimal(str(ss_emp.get("total_eur", ss_emp.get("total_ss_empresa", 0))))
        coste_total_mensual = _r2(devengos_salariales + total_ss_emp)

        # === BASES NOMINA (layout oficial) ===
        bases = {
            "base_cc": float(base_cotizacion),
            "base_at_ep": float(base_cotizacion),
            "base_desempleo": float(base_cotizacion),
            "base_fp": float(base_cotizacion),
            "base_irpf": float(_r2(devengos_salariales)),
            "base_he": float(_r2(he)) if he > 0 else 0,
        }

        return {
            "periodo": date.today().strftime("%m/%Y"),
            "devengos": {
                "salario_base": float(_r2(bruto)),
                "complemento_productividad": float(_r2(productividad)),
                "horas_extras": float(_r2(he)),
                "plus_transporte_exento": float(_r2(transporte)),
                "plus_comida_exento": float(_r2(comida)),
                "total_devengado": float(total_devengado),
            },
            "deducciones": {
                "ss_contingencias_comunes": ss_trab["contingencias_comunes"],
                "ss_desempleo": ss_trab["desempleo"],
                "ss_formacion_profesional": ss_trab["formacion_profesional"],
                "ss_horas_extras": ss_trab["horas_extras"],
                "total_ss_trabajador": float(total_ss_trab),
                "irpf": float(irpf_mensual),
                "irpf_tipo_pct": float(tipo_irpf),
                "total_deducciones": float(total_deducciones),
            },
            "liquido_percibir": float(neto_mensual),
            "coste_empresa": {
                "salario_bruto": float(_r2(devengos_salariales)),
                "ss_empresa": ss_emp,
                "coste_total_mensual": float(coste_total_mensual),
                "coste_total_anual": float(_r2(coste_total_mensual * num_pagas)),
            },
            "bases": bases,
            "irpf_detalle": irpf_result,
            "metadata": {
                "tipo_contrato": tipo_contrato,
                "num_pagas": num_pagas,
                "situacion_familiar": situacion_familiar,
                "comunidad_autonoma": comunidad_autonoma,
                "categoria_profesional": categoria_profesional,
                "antiguedad_anos": antiguedad_anos,
            },
        }

    def _calcular_base(
        self, devengos: Decimal, transporte: Decimal, comida: Decimal, grupo_ss: str = ""
    ) -> Decimal:
        base = devengos
        exento_transporte = min(transporte, Decimal("1500") / 12)
        exento_comida = min(comida, Decimal("12.20") * 22)
        base = _r2(base - exento_transporte - exento_comida)
        # Aplicar topes por grupo de cotización si SSCalculator disponible
        if self.ss:
            base = Decimal(str(self.ss._apply_topes(float(base), grupo_ss)))
        else:
            # Topes genéricos 2026 — Orden PJC/297/2026
            base = max(Decimal("1424.50"), min(base, Decimal("5101.20")))
        return base

    def _ss_trabajador(self, base: Decimal, tipo_contrato: str, he: Decimal) -> dict:
        temporal = tipo_contrato in ("temporal", "formacion", "practicas", "interinidad")
        tasa_cc = Decimal("0.0470")
        tasa_des = Decimal("0.0160") if temporal else Decimal("0.0155")
        tasa_fp = Decimal("0.0010")
        tasa_mei = Decimal("0.0015")
        tasa_he = Decimal("0.0200")

        cc = _r2(base * tasa_cc)
        des = _r2(base * tasa_des)
        fp = _r2(base * tasa_fp)
        mei = _r2(base * tasa_mei)
        he_importe = _r2(he * tasa_he) if he > 0 else Decimal("0")
        total = _r2(cc + des + fp + mei + he_importe)

        return {
            "contingencias_comunes": float(cc),
            "desempleo": float(des),
            "formacion_profesional": float(fp),
            "mei": float(mei),
            "horas_extras": float(he_importe),
            "total_ss_trabajador": float(total),
        }

    def _ss_empresa(
        self, base: Decimal, tipo_contrato: str, cnae: str, he: Decimal, category: str = ""
    ) -> dict:
        if self.ss:
            result = self.ss.calculate(
                float(base), tipo_contrato, category=category, contract_days=None
            )
            return result.to_dict()
        temporal = tipo_contrato in ("temporal", "formacion", "practicas")
        tasa_cc = Decimal("0.2360")
        tasa_des = Decimal("0.0670") if temporal else Decimal("0.0550")
        tasa_fogasa = Decimal("0.0020")
        tasa_fp = Decimal("0.0060")
        tasa_atep = Decimal("0.0150")
        tasa_mei = Decimal("0.0075")

        cc = _r2(base * tasa_cc)
        des = _r2(base * tasa_des)
        fogasa = _r2(base * tasa_fogasa)
        fp = _r2(base * tasa_fp)
        atep = _r2(base * tasa_atep)
        mei = _r2(base * tasa_mei)
        total = _r2(cc + des + fogasa + fp + atep + mei)

        return {
            "contingencias_comunes": float(cc),
            "desempleo": float(des),
            "fogasa": float(fogasa),
            "formacion_profesional": float(fp),
            "atep": float(atep),
            "mei": float(mei),
            "total_ss_empresa": float(total),
        }
