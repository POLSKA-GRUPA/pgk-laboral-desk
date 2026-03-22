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
    monthly_14_payments_eur: float
    annual_eur: float
    hourly_ordinary_or_flexible_eur: float


class LaboralEngine:
    """Motor principal de cálculo laboral."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.salary_rows = [SalaryRow(**row) for row in data["salarios_por_categoria"]]
        self.condition_index = {
            self._normalize(item["label"]): item
            for section in data["sections"]
            for item in section["items"]
        }
        self.categories_list = [row.category for row in self.salary_rows]
        self.ss = SSCalculator()
        self.irpf = IRPFEstimator()

    @classmethod
    def from_json_file(cls, path: str | Path | None = None) -> "LaboralEngine":
        p = Path(path) if path else DEFAULT_DATA_FILE
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(data)

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
        base_mensual = round(row.monthly_14_payments_eur * jornada_ratio, 2)
        antiguedad = round(base_mensual * 0.03 * trienios, 2)
        plus_transporte = self._get_plus_transporte()
        prorrata_extras = round(base_mensual / 6.0, 2) if extras_prorated else 0.0

        bruto_mensual = round(
            base_mensual + antiguedad + plus_transporte + prorrata_extras, 2
        )

        # 5. Bruto anual
        num_pagas = 12 if extras_prorated else 14
        if extras_prorated:
            bruto_anual = round(bruto_mensual * 12, 2)
        else:
            mensual_ordinario = base_mensual + antiguedad + plus_transporte
            paga_extra = base_mensual + antiguedad  # Art. 31: 30 días salario convenio
            bruto_anual = round(mensual_ordinario * 12 + paga_extra * 2, 2)

        # 6. Seguridad Social (con grupo de cotización y recargo contratos cortos)
        ss_result = self.ss.calculate(
            base_mensual_bruta=bruto_mensual,
            contract_type=contract_type,
            at_ep_pct=at_ep_pct,
            category=row.category,
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
            "pagas": "12 (prorrateadas)" if extras_prorated else "14",

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
            "fuentes": [
                "Convenio colectivo estatal de mantenimiento y conservación de instalaciones acuáticas (BOE-A-2026-5849)",
                "Anexo I salarial — tablas 2025",
                "Orden PJC/51/2025 de cotización SS",
                "Arts. 80-86 RIRPF (retención estimada)",
            ],

            # Notas
            "notas": self._build_notas(
                at_ep_used, irpf_result.region, ss_result.grupo_cotizacion, recargo
            ),

            # Condiciones relevantes
            "condiciones_convenio": self._select_conditions(contract_type),
        }

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
