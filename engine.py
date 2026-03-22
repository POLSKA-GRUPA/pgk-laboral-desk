"""Motor de cálculo laboral — PGK Laboral Desk.

Toma los datos del convenio cargado, calcula devengos, aplica SS
(empresa + trabajador) e IRPF estimado, y devuelve:
  - Coste total empresa / mes y / año
  - Salario bruto mensual
  - Deducciones trabajador (SS + IRPF)
  - Neto estimado trabajador

Todo trazable a artículos del convenio.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_calculator import SSCalculator
from irpf_estimator import IRPFEstimator, SUPPORTED_REGIONS


FULL_TIME_WEEKLY_HOURS = 40.0

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = APP_ROOT / "data" / "convenio_acuaticas_2025_2027.json"

CONTRACT_LABELS: dict[str, str] = {
    "indefinido": "Indefinido",
    "fijo-discontinuo": "Fijo-discontinuo",
    "temporal": "Temporal",
    "temporal-produccion": "Temporal por circ. de la producción",
    "sustitucion": "Sustitución",
    "tiempo-parcial": "Tiempo parcial",
}


@dataclass(frozen=True)
class SalaryRow:
    section: str
    category: str
    annual_eur: float
    monthly_base_eur: float  # mensual base (anual / num_pagas)
    num_pagas: int
    grupo_ss: str = ""
    hourly_ordinary_or_flexible_eur: float = 0.0


class LaboralEngine:
    """Motor principal de cálculo laboral."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        # Detectar número de pagas del convenio
        resumen = data.get("resumen_operativo", {})
        self._convenio_pagas = resumen.get("pagas_extras", 2) + 12  # 14 o 15
        self.salary_rows = self._parse_salary_rows(data)
        self.condition_index = {
            self._normalize(item["label"]): item
            for section in data["sections"]
            for item in section["items"]
        }
        self.categories_list = [row.category for row in self.salary_rows]
        self.ss = SSCalculator()
        self.irpf = IRPFEstimator()

    def _parse_salary_rows(self, data: dict[str, Any]) -> list[SalaryRow]:
        """Parsea salarios soportando ambos schemas (14 o 15 pagas)."""
        rows: list[SalaryRow] = []
        for raw in data["salarios_por_categoria"]:
            annual = raw.get("annual_eur")
            if annual is None:  # Grupo 6 Nivel 2 = SMI
                continue
            # Detectar campo mensual: monthly_14 o monthly_15
            monthly = (
                raw.get("monthly_14_payments_eur")
                or raw.get("monthly_15_payments_eur")
            )
            if monthly is None and annual:
                monthly = round(annual / self._convenio_pagas, 2)
            rows.append(SalaryRow(
                section=raw.get("section", ""),
                category=raw["category"],
                annual_eur=annual,
                monthly_base_eur=monthly,
                num_pagas=self._convenio_pagas,
                grupo_ss=raw.get("grupo_ss", ""),
                hourly_ordinary_or_flexible_eur=raw.get("hourly_ordinary_or_flexible_eur", 0.0),
            ))
        return rows

    @classmethod
    def from_json_file(cls, path: str | Path | None = None) -> "LaboralEngine":
        p = Path(path) if path else DEFAULT_DATA_FILE
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(data)

    @classmethod
    def from_convenio_id(cls, convenio_id: str) -> "LaboralEngine":
        """Carga un convenio por su ID (nombre del JSON sin extensión)."""
        p = APP_ROOT / "data" / f"{convenio_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"Convenio no encontrado: {convenio_id}")
        return cls.from_json_file(p)

    @staticmethod
    def list_available_convenios() -> list[dict[str, Any]]:
        """Lista convenios disponibles en data/."""
        convenios: list[dict[str, Any]] = []
        for f in sorted((APP_ROOT / "data").glob("convenio_*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                c = d.get("convenio", {})
                convenios.append({
                    "id": f.stem,
                    "nombre": c.get("nombre", f.stem),
                    "ambito": c.get("ambito", "estatal"),
                    "vigencia": f"{c.get('vigencia_desde_ano', '?')}–{c.get('vigencia_hasta_ano', '?')}",
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return convenios

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def get_categories(self) -> list[dict[str, str]]:
        """Lista de categorías para el select del formulario."""
        return [
            {"value": row.category, "label": row.category.rstrip(".")}
            for row in self.salary_rows
        ]

    def get_contract_types(self) -> list[dict[str, str]]:
        """Tipos de contrato disponibles."""
        return [{"value": k, "label": v} for k, v in CONTRACT_LABELS.items()]

    def get_regions(self) -> list[dict[str, str]]:
        """Regiones IRPF disponibles."""
        labels = {
            "generica": "Genérica (media estatal)",
            "madrid": "Madrid",
            "cataluna": "Cataluña",
            "andalucia": "Andalucía",
            "valencia": "C. Valenciana",
        }
        return [{"value": r, "label": labels.get(r, r)} for r in SUPPORTED_REGIONS]

    def simulate(
        self,
        category: str,
        contract_type: str = "indefinido",
        weekly_hours: float = 40.0,
        seniority_years: int = 0,
        extras_prorated: bool = False,
        num_children: int = 0,
        children_under_3: int = 0,
        at_ep_pct: float | None = None,
        region: str = "generica",
        contract_days: int | None = None,
    ) -> dict[str, Any]:
        """Simulación completa de coste de contratación."""

        # 1. Buscar categoría
        row = self._find_category(category)
        if row is None:
            return {"error": f"Categoría no encontrada: {category}"}

        # 2. Jornada
        jornada_ratio = round(weekly_hours / FULL_TIME_WEEKLY_HOURS, 4)

        # 3. Trienios (Art. 32)
        trienios = math.floor(seniority_years / 3)

        # 4. Devengos mensuales
        base_mensual = round(row.monthly_base_eur * jornada_ratio, 2)
        antiguedad = round(base_mensual * 0.03 * trienios, 2)
        plus_transporte = self._get_plus_transporte()
        n_extras = self._convenio_pagas - 12  # 2 o 3 pagas extras
        prorrata_extras = round(base_mensual * n_extras / 12.0, 2) if extras_prorated else 0.0

        bruto_mensual = round(
            base_mensual + antiguedad + plus_transporte + prorrata_extras, 2
        )

        # 5. Bruto anual
        num_pagas = 12 if extras_prorated else self._convenio_pagas
        if extras_prorated:
            bruto_anual = round(bruto_mensual * 12, 2)
        else:
            mensual_ordinario = base_mensual + antiguedad + plus_transporte
            paga_extra = base_mensual + antiguedad
            bruto_anual = round(mensual_ordinario * 12 + paga_extra * n_extras, 2)

        # 6. Seguridad Social (con grupo de cotización y recargo contratos cortos)
        ss_category = row.grupo_ss or row.category
        ss_result = self.ss.calculate(
            base_mensual_bruta=bruto_mensual,
            contract_type=contract_type,
            at_ep_pct=at_ep_pct,
            category=ss_category,
            contract_days=contract_days,
        )

        # 7. IRPF estimado (con CC.AA.)
        meses_cotizacion = 12 if extras_prorated else 14
        annual_ss_worker = round(ss_result.trab_total * meses_cotizacion, 2)
        irpf_result = self.irpf.estimate(
            annual_gross=bruto_anual,
            annual_ss_worker=annual_ss_worker,
            num_children=num_children,
            children_under_3=children_under_3,
            contract_type=contract_type,
            num_payments=num_pagas,
            region=region,
        )

        # 8. Neto mensual estimado
        neto_mensual = round(
            bruto_mensual - ss_result.trab_total - irpf_result.monthly_retention, 2
        )

        # 9. Coste empresa (incluye recargo contrato corto si aplica)
        recargo = ss_result.recargo_contrato_corto
        coste_empresa_mes = round(bruto_mensual + ss_result.emp_total + recargo, 2)
        if extras_prorated:
            coste_empresa_anual = round(coste_empresa_mes * 12, 2)
        else:
            coste_empresa_anual = round(
                coste_empresa_mes * 12
                + (paga_extra + ss_result.emp_total) * 2,
                2,
            )

        # 10. Devengos detallados
        devengos = [
            {"concepto": "Salario base convenio", "eur": base_mensual, "fuente": "Art. 30 y Anexo I"},
        ]
        if antiguedad > 0:
            devengos.append({
                "concepto": f"Antigüedad ({trienios} trienios × 3%)",
                "eur": antiguedad,
                "fuente": "Art. 32",
            })
        devengos.append({"concepto": "Plus transporte", "eur": plus_transporte, "fuente": "Art. 33 y Anexo I"})
        if extras_prorated:
            devengos.append({"concepto": "Prorrata pagas extra", "eur": prorrata_extras, "fuente": "Art. 31"})

        at_ep_used = at_ep_pct if at_ep_pct is not None else self.ss.config["empresa"]["at_ep_default"]

        return {
            # Resumen
            "categoria": row.category.rstrip("."),
            "contrato": CONTRACT_LABELS.get(contract_type, contract_type),
            "contrato_tipo": contract_type,
            "jornada_horas": weekly_hours,
            "jornada_pct": round(jornada_ratio * 100, 1),
            "antiguedad_anos": seniority_years,
            "trienios": trienios,
            "pagas": "12 (prorrateadas)" if extras_prorated else str(self._convenio_pagas),

            # Cifras clave
            "coste_total_empresa_mes_eur": coste_empresa_mes,
            "coste_total_empresa_anual_eur": coste_empresa_anual,
            "bruto_mensual_eur": bruto_mensual,
            "bruto_anual_eur": bruto_anual,
            "ss_empresa_mes_eur": round(ss_result.emp_total, 2),
            "ss_trabajador_mes_eur": round(ss_result.trab_total, 2),
            "irpf_retencion_pct": round(irpf_result.retention_rate_pct, 2),
            "irpf_mensual_eur": round(irpf_result.monthly_retention, 2),
            "neto_mensual_eur": neto_mensual,
            "grupo_cotizacion_ss": ss_result.grupo_cotizacion,
            "region_irpf": irpf_result.region,

            # Desglose
            "devengos": devengos,
            "ss_detalle": ss_result.to_dict(),
            "irpf_detalle": irpf_result.to_dict(),

            # Convenio
            "convenio": self.data["convenio"],
            "fuentes": self._build_fuentes(),

            # Notas
            "notas": self._build_notas(
                at_ep_used, irpf_result.region, ss_result.grupo_cotizacion, recargo
            ),

            # Condiciones relevantes
            "condiciones_convenio": self._select_conditions(contract_type),
        }

    # ------------------------------------------------------------------
    # Calculadora de despido / extinción laboral
    # ------------------------------------------------------------------

    _TIPOS_DESPIDO: dict[str, dict] = {
        "improcedente": {
            "label": "Despido improcedente",
            "dias_por_año": 33,
            "max_meses": 24,
            "descripcion": "Empresa rescinde sin causa justificada o ésta no se prueba.",
        },
        "objetivo": {
            "label": "Despido objetivo (Art. 52 ET)",
            "dias_por_año": 20,
            "max_meses": 12,
            "descripcion": "Causas económicas, técnicas, organizativas o de producción.",
        },
        "disciplinario": {
            "label": "Despido disciplinario (pendiente de sentencia)",
            "dias_por_año": 33,
            "max_meses": 24,
            "descripcion": "Incumplimiento grave del trabajador. Si se prueba: 0€. Si no: 33 días/año.",
        },
        "disciplinario_procedente": {
            "label": "Despido disciplinario procedente",
            "dias_por_año": 0,
            "max_meses": 0,
            "descripcion": "Causa probada en juicio o aceptada. No hay indemnización.",
        },
        "mutuo_acuerdo": {
            "label": "Mutuo acuerdo / extinción consensual",
            "dias_por_año": 20,
            "max_meses": 12,
            "descripcion": "Acuerdo entre ambas partes. Punto de partida: coste despido objetivo.",
        },
        "voluntario": {
            "label": "Baja voluntaria del trabajador",
            "dias_por_año": 0,
            "max_meses": 0,
            "descripcion": "El trabajador decide marcharse. Sin indemnización para él.",
        },
        "ere": {
            "label": "ERE / extinción colectiva",
            "dias_por_año": 20,
            "max_meses": 12,
            "descripcion": "Despido colectivo con autorización. Mínimo legal: 20 días/año.",
        },
    }

    def calcular_despido(
        self,
        tipo_despido: str,
        fecha_inicio: str,
        salario_bruto_mensual: float,
        fecha_despido: str | None = None,
        dias_vacaciones_pendientes: int = 0,
        dias_preaviso_empresa: int = 0,
        weekly_hours: float = 40.0,
        nombre_trabajador: str = "",
        categoria: str = "",
    ) -> dict[str, Any]:
        """Calcula el coste total de una extinción laboral con consejo estratégico."""
        from datetime import date

        fecha_inicio_dt = date.fromisoformat(fecha_inicio)
        fecha_despido_dt = date.fromisoformat(fecha_despido) if fecha_despido else date.today()

        if fecha_despido_dt <= fecha_inicio_dt:
            return {"error": "La fecha de despido debe ser posterior a la fecha de inicio."}

        # Antigüedad
        dias_totales = (fecha_despido_dt - fecha_inicio_dt).days
        antiguedad_anos = dias_totales / 365.25
        jornada_ratio = weekly_hours / FULL_TIME_WEEKLY_HOURS

        # Salario diario (sobre bruto anual estimado)
        bruto_anual = salario_bruto_mensual * self._convenio_pagas
        salario_diario = bruto_anual / 365.0

        tipo_info = self._TIPOS_DESPIDO.get(tipo_despido, self._TIPOS_DESPIDO["improcedente"])
        dias_por_año = tipo_info["dias_por_año"]
        max_meses = tipo_info["max_meses"]

        # Indemnización
        if dias_por_año > 0:
            indemnizacion_raw = salario_diario * dias_por_año * antiguedad_anos
            tope = salario_bruto_mensual * max_meses
            indemnizacion = round(min(indemnizacion_raw, tope), 2)
            tope_aplicado = indemnizacion < indemnizacion_raw
        else:
            indemnizacion = 0.0
            indemnizacion_raw = 0.0
            tope = 0.0
            tope_aplicado = False

        # Finiquito — 1. Salario días pendientes del mes en curso
        dias_mes = fecha_despido_dt.day
        salario_dias_pendientes = round(salario_diario * dias_mes, 2)

        # Finiquito — 2. Parte proporcional pagas extra
        year_start = date(fecha_despido_dt.year, 1, 1)
        dias_trabajados_ano = (fecha_despido_dt - year_start).days + 1
        n_extras = self._convenio_pagas - 12
        pp_pagas = round((dias_trabajados_ano / 365.0) * (salario_bruto_mensual * n_extras), 2)

        # Finiquito — 3. Vacaciones pendientes (usuario informa los días que quedan)
        vacaciones_eur = round(dias_vacaciones_pendientes * salario_diario, 2)

        # Finiquito — 4. Preaviso no cumplido por la empresa (solo despidos con preaviso obligatorio)
        preaviso_convenio_dias = 15  # ET Art. 53 para objetivo; convenio para voluntario
        if tipo_despido in ("objetivo", "ere"):
            preaviso_pendiente_dias = max(0, preaviso_convenio_dias - dias_preaviso_empresa)
            preaviso_eur = round(preaviso_pendiente_dias * salario_diario, 2)
        else:
            preaviso_pendiente_dias = 0
            preaviso_eur = 0.0

        total_finiquito = round(salario_dias_pendientes + pp_pagas + vacaciones_eur + preaviso_eur, 2)
        total_eur = round(indemnizacion + total_finiquito, 2)

        # Escenarios alternativos (para contexto del director)
        esc_objetivo = round(min(salario_diario * 20 * antiguedad_anos, salario_bruto_mensual * 12), 2)
        esc_improcedente = round(min(salario_diario * 33 * antiguedad_anos, salario_bruto_mensual * 24), 2)

        return {
            "nombre_trabajador": nombre_trabajador,
            "categoria": categoria,
            "tipo_despido": tipo_despido,
            "tipo_despido_label": tipo_info["label"],
            "tipo_despido_desc": tipo_info["descripcion"],
            "fecha_inicio": fecha_inicio,
            "fecha_despido": fecha_despido_dt.isoformat(),
            "antiguedad_anos": round(antiguedad_anos, 2),
            "antiguedad_dias": dias_totales,
            "salario_bruto_mensual_eur": round(salario_bruto_mensual, 2),
            "salario_diario_eur": round(salario_diario, 2),
            "jornada_horas": weekly_hours,
            # Indemnización
            "indemnizacion_eur": indemnizacion,
            "indemnizacion_calculo": (
                f"{dias_por_año} días/año × {round(antiguedad_anos, 2)} años × {round(salario_diario, 2)}€/día"
                if dias_por_año > 0 else "No corresponde indemnización"
            ),
            "indemnizacion_raw_eur": round(indemnizacion_raw, 2),
            "tope_maximo_eur": round(tope, 2),
            "tope_aplicado": tope_aplicado,
            # Finiquito desglosado
            "finiquito": {
                "salario_dias_pendientes_eur": salario_dias_pendientes,
                "salario_dias_pendientes_n": dias_mes,
                "parte_proporcional_pagas_eur": pp_pagas,
                "parte_proporcional_pagas_n": n_extras,
                "vacaciones_pendientes_eur": vacaciones_eur,
                "vacaciones_pendientes_dias": dias_vacaciones_pendientes,
                "preaviso_pendiente_eur": preaviso_eur,
                "preaviso_pendiente_dias": preaviso_pendiente_dias,
                "total_finiquito_eur": total_finiquito,
            },
            "total_eur": total_eur,
            # Comparativa escenarios
            "escenarios": {
                "objetivo_eur": esc_objetivo,
                "improcedente_eur": esc_improcedente,
            },
            "consejo": self._build_consejo_despido(
                tipo_despido, antiguedad_anos, indemnizacion,
                salario_bruto_mensual, salario_diario, esc_improcedente, esc_objetivo,
            ),
            "fuentes": [
                "Arts. 49-56 ET (Estatuto de los Trabajadores)",
                f"{self.data['convenio'].get('nombre', 'Convenio aplicable')}",
                "Orden de cotización SS 2026",
            ],
            "notas": [
                "Cálculo orientativo. Confirmar siempre con asesoría laboral antes de actuar.",
                "La antigüedad se computa desde la fecha de inicio del primer contrato, aunque haya habido renovaciones sin interrupción.",
                "Para trabajadores contratados antes del 12/02/2012, la indemnización por despido improcedente tiene un régimen transitorio (45 días/año hasta esa fecha, con tope de 42 mensualidades).",
            ],
        }

    def get_tipos_despido(self) -> list[dict[str, Any]]:
        """Lista de tipos de despido para el selector."""
        return [
            {
                "value": k,
                "label": v["label"],
                "descripcion": v["descripcion"],
                "dias_por_año": v["dias_por_año"],
            }
            for k, v in self._TIPOS_DESPIDO.items()
        ]

    def _build_consejo_despido(
        self,
        tipo: str,
        anos: float,
        indemnizacion: float,
        mensual: float,
        salario_diario: float,
        imp_eur: float,
        obj_eur: float,
    ) -> list[str]:
        consejos = []
        preaviso = 15

        if tipo == "improcedente":
            consejos.append(
                f"La empresa paga {indemnizacion:,.2f}€ de indemnización (33 días/año × {anos:.1f} años)."
            )
            consejos.append(
                "El despido improcedente puede ofrecerse voluntariamente (evita juicio) "
                "o ser declarado por el juez si el trabajador impugna."
            )
            if anos < 1:
                consejos.append("Con menos de 1 año, la indemnización es proporcional a los meses trabajados.")

        elif tipo == "objetivo":
            consejos.append(
                f"Requiere carta de despido con causa económica/técnica/organizativa y {preaviso} días de preaviso obligatorio."
            )
            consejos.append(
                f"Si el juzgado rechaza la causa o no se respeta el preaviso, el despido pasa a improcedente: coste subiría a {imp_eur:,.2f}€."
            )
            consejos.append(
                "Causas válidas (Art. 52 ET): pérdidas actuales o previstas, disminución persistente de ingresos, "
                "cambios en demanda de productos/servicios. Deben estar documentadas."
            )

        elif tipo == "disciplinario":
            consejos.append(
                f"Si el despido es declarado PROCEDENTE: 0€ de indemnización. "
                f"Si es IMPROCEDENTE: {imp_eur:,.2f}€."
            )
            consejos.append(
                "Para que sea procedente, el incumplimiento debe ser grave y culpable, y estar tipificado "
                "en el Art. 54 ET o en el convenio. La carta de despido debe describir los hechos con precisión."
            )
            consejos.append(
                "Recomendación: antes de actuar, documenta el incumplimiento (advertencias previas, partes, correos). "
                "Un despido disciplinario mal ejecutado sale más caro que uno objetivo."
            )

        elif tipo == "disciplinario_procedente":
            consejos.append("Despido disciplinario con causa probada: 0€ de indemnización.")
            consejos.append(
                "El trabajador tiene 20 días hábiles para impugnar el despido desde la fecha de efectos. "
                "Guarda toda la documentación del expediente por si hay juicio."
            )

        elif tipo == "mutuo_acuerdo":
            consejos.append(
                f"No hay mínimo legal — es negociado. Punto de partida habitual: coste del despido objetivo ({obj_eur:,.2f}€)."
            )
            consejos.append(
                "Atención: el trabajador NO puede cobrar el desempleo tras un mutuo acuerdo (salvo ERE homologado). "
                "Esto puede ser un argumento en la negociación — el trabajador asume ese coste."
            )
            consejos.append(
                "Ventajas para la empresa: evita riesgo de juicio, se negocia la fecha exacta de salida, "
                "y se puede acordar confidencialidad."
            )

        elif tipo == "voluntario":
            consejos.append(
                f"La baja voluntaria no genera coste de indemnización para la empresa."
            )
            consejos.append(
                f"El trabajador debe respetar el preaviso de {preaviso} días (convenio aplicable). "
                f"Si no lo hace, puedes descontar esos días de la liquidación: {round(salario_diario * preaviso, 2):,.2f}€."
            )
            consejos.append(
                "El trabajador NO puede cobrar el desempleo. "
                "Si el trabajador amenaza con irse pero en realidad quiere ser despedido, "
                "considera si te interesa el mutuo acuerdo (más caro para ti, pero él obtiene el paro)."
            )

        elif tipo == "ere":
            consejos.append(
                f"ERE: mínimo 20 días/año (máx. 12 mensualidades). Coste mínimo: {indemnizacion:,.2f}€ por trabajador."
            )
            consejos.append(
                "Requiere período de consultas con representantes de los trabajadores (mín. 15 días para empresas < 50 trabajadores)."
            )
            consejos.append(
                "Las prestaciones por desempleo en ERE tienen condiciones especiales. Asesórate antes de iniciar el procedimiento."
            )

        return consejos

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @staticmethod
    def _build_notas(
        at_ep_pct: float, region: str, grupo: str, recargo: float,
    ) -> list[str]:
        notas = []
        if region and region != "generica":
            notas.append(f"IRPF calculado con escala autonómica: {region}.")
        else:
            notas.append("IRPF estimado con escala genérica (media estatal). Ajustar según CC.AA.")
        notas.append(f"AT/EP aplicado: {at_ep_pct:.2f}%. Verificar tarifa real según CNAE.")
        if grupo:
            notas.append(f"Grupo de cotización SS: {grupo}.")
        if recargo > 0:
            notas.append(f"Recargo contrato ≤30 días: {recargo:.2f}€ (DA 7ª ET).")
        notas.append("Pre-nómina orientativa. No sustituye validación profesional.")
        return notas

    def _build_fuentes(self) -> list[str]:
        conv = self.data.get("convenio", {})
        nombre = conv.get("nombre", "Convenio cargado")
        fuentes = [nombre]
        if conv.get("anexo_salarial_ano"):
            fuentes.append(f"Anexo salarial — tablas {conv['anexo_salarial_ano']}")
        fuentes.append("Orden cotización SS 2026")
        fuentes.append("Arts. 80-86 RIRPF (retención estimada)")
        return fuentes

    def _find_category(self, category: str) -> SalaryRow | None:
        for row in self.salary_rows:
            if row.category == category or row.category.rstrip(".") == category.rstrip("."):
                return row
        return None

    def _get_plus_transporte(self) -> float:
        item = self.condition_index.get(self._normalize("plus transporte"))
        if not item:
            return 0.0
        match = re.search(r"(\d+(?:\.\d+)?)\s*EUR", item["detail"])
        return float(match.group(1)) if match else 0.0

    def _select_conditions(self, contract_type: str) -> list[dict[str, Any]]:
        titles = {
            "Contratación y modalidad",
            "Jornada y descansos",
            "Retribución",
            "Vacaciones, permisos y coberturas",
        }
        if contract_type == "fijo-discontinuo":
            titles.add("Alertas de aplicación")
        return [s for s in self.data["sections"] if s["title"] in titles]

    @staticmethod
    def _normalize(value: str) -> str:
        v = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
        v = re.sub(r"[^a-z0-9]+", " ", v)
        return re.sub(r"\s+", " ", v).strip()
