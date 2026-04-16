"""Motor de auditoría de nóminas D1-D7 — PGK Laboral Desk.

Compara datos parseados desde PDFs de nóminas contra valores esperados
calculados por los motores de SS, IRPF y convenio, produciendo hallazgos
clasificados por severidad.

Dimensiones de auditoría:
- D1: Integridad aritmética (sumas cuadran)
- D2: Cumplimiento legal SS (tasas, topes 2026)
- D3: IRPF razonabilidad
- D4: Cumplimiento convenio colectivo
- D5: Coherencia inter-trabajador
- D6: Consistencia temporal (mes a mes)
- D7: Embargos y retenciones (LEC art.607)

Fuentes legales:
- Orden ISM/31/2026 (BOE-A-2026-1921) — bases y topes cotización 2026
- RDL 3/2026 — MEI 2026: 0,90% total
- Art.607 LEC — límites embargo salarios
- Convenio colectivo aplicable (por categoría)
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.audit_schemas import (
    AuditFinding,
    AuditReport,
    WorkerAuditResult,
)
from app.services.nomina_audit_parser import ParsedNomina

_TOLERANCE = 0.02

# Tasas SS trabajador 2026 — Orden ISM/31/2026 + RDL 3/2026
SS_TRAB_EXPECTED = {
    "cc": 4.70,
    "desempleo": 1.55,
    "fp": 0.10,
    "mei": 0.15,
}

# Tasas SS empresa 2026 (indefinido)
SS_EMP_EXPECTED = {
    "cc": 24.35,
    "at_ep_default": 1.85,
    "desempleo": 5.50,
    "fp": 0.60,
    "fogasa": 0.20,
}

# Topes cotización 2026 — Orden ISM/31/2026
BASE_MIN_2026 = 1424.50
BASE_MAX_2026 = 5101.20

# SMI 2026 para cálculo inembargable
SMI_MENSUAL_2026 = 1424.50


class NominaAuditEngine:
    """Motor de auditoría de nóminas con 7 dimensiones de verificación."""

    def __init__(
        self,
        convenio_data: dict[str, Any] | None = None,
        ss_config_path: str | None = None,
    ) -> None:
        self.convenio_data = convenio_data or {}
        self._salarios_por_categoria: dict[str, dict[str, Any]] = {}
        self._plus_transporte = 0.0
        if self.convenio_data:
            self._index_convenio()

    def _index_convenio(self) -> None:
        for row in self.convenio_data.get("salarios_por_categoria", []):
            cat = row.get("category", "").rstrip(".")
            self._salarios_por_categoria[cat] = row
            if row.get("grupo_ss"):
                self._salarios_por_categoria[row["grupo_ss"]] = row

        for section in self.convenio_data.get("sections", []):
            for item in section.get("items", []):
                label = item.get("label", "").lower()
                if "plus transporte" in label or "transporte" in label:
                    detail = item.get("detail", "")
                    import re

                    m = re.search(r"(\d+(?:[.,]\d+)?)\s*EUR", detail)
                    if m:
                        self._plus_transporte = float(m.group(1).replace(",", "."))

    def audit_month(
        self,
        nominas: list[ParsedNomina],
        previous_month: list[ParsedNomina] | None = None,
    ) -> AuditReport:
        if not nominas:
            return AuditReport(empresa="", cif="", ccc="", convenio="", periodo="")

        first = nominas[0]
        periodo = f"{first.periodo_mes} {first.periodo_anio}"
        report = AuditReport(
            empresa=first.empresa_nombre,
            cif=first.empresa_cif,
            ccc=first.empresa_ccc,
            convenio=self.convenio_data.get("convenio", {}).get("nombre", ""),
            periodo=periodo,
            audit_timestamp=datetime.now().isoformat(),
        )

        prev_by_name: dict[str, ParsedNomina] = {}
        if previous_month:
            prev_by_name = {n.nombre_trabajador: n for n in previous_month}

        for nom in nominas:
            worker = WorkerAuditResult(
                worker_name=nom.nombre_trabajador,
                nif=nom.nif,
                grupo_profesional=nom.grupo_profesional,
                grupo_cotizacion=nom.grupo_cotizacion,
                periodo=periodo,
                total_devengado=nom.total_devengado,
                liquido=nom.liquido,
                coste_empresa=nom.coste_total_empresa,
                parse_errors=list(nom.parse_errors),
            )

            findings: list[AuditFinding] = []
            findings.extend(self._d1_arithmetic(nom, periodo))
            findings.extend(self._d2_ss_legal(nom, periodo))
            findings.extend(self._d3_irpf(nom, periodo))
            findings.extend(self._d4_convenio(nom, periodo))
            findings.extend(self._d7_embargos(nom, periodo))

            prev = prev_by_name.get(nom.nombre_trabajador)
            if prev:
                findings.extend(self._d6_temporal(nom, prev, periodo))

            worker.findings = findings
            report.workers.append(worker)

        report.findings = self._d5_inter_worker(nominas, periodo)
        report.summary = self._compute_summary(report)

        return report

    def audit_trimester(self, trimester_data: dict[str, list[ParsedNomina]]) -> AuditReport:
        months = sorted(trimester_data.keys())
        if not months:
            return AuditReport(empresa="", cif="", ccc="", convenio="", periodo="")

        all_nominas: list[ParsedNomina] = []
        for m in months:
            all_nominas.extend(trimester_data[m])

        if not all_nominas:
            return AuditReport(empresa="", cif="", ccc="", convenio="", periodo="")

        periodo = f"{months[0]}-{months[-1]} {all_nominas[0].periodo_anio}"
        report = AuditReport(
            empresa=all_nominas[0].empresa_nombre,
            cif=all_nominas[0].empresa_cif,
            ccc=all_nominas[0].empresa_ccc,
            convenio=self.convenio_data.get("convenio", {}).get("nombre", ""),
            periodo=periodo,
            audit_timestamp=datetime.now().isoformat(),
        )

        month_list = list(trimester_data.values())
        for i, month_nominas in enumerate(month_list):
            prev = month_list[i - 1] if i > 0 else None
            month_report = self.audit_month(month_nominas, prev)
            for w in month_report.workers:
                existing = next(
                    (ew for ew in report.workers if ew.worker_name == w.worker_name),
                    None,
                )
                if existing:
                    existing.findings.extend(w.findings)
                    existing.parse_errors.extend(w.parse_errors)
                else:
                    report.workers.append(w)

        report.findings = self._d5_inter_worker(all_nominas, periodo)
        report.summary = self._compute_summary(report)
        return report

    # ── D1: Integridad aritmética ──

    def _d1_arithmetic(self, nom: ParsedNomina, periodo: str) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        dim = "D1_arithmetic"

        # Suma devengos
        suma_devengos = sum(d.importe for d in nom.devengos)
        if abs(suma_devengos - nom.total_devengado) > _TOLERANCE:
            findings.append(
                self._make_finding(
                    code="D1-001",
                    dimension=dim,
                    severity="high",
                    confidence=95,
                    title="Suma devengos != Total devengado",
                    description=f"La suma de devengos individuales ({suma_devengos:.2f} EUR) no coincide con el total devengado ({nom.total_devengado:.2f} EUR). Posible concepto no capturado por el parser o error en el PDF.",
                    nom=nom,
                    periodo=periodo,
                    expected=nom.total_devengado,
                    actual=suma_devengos,
                    reference="Layout nómina Sage/A3 — sección I",
                    fix="Verificar si el parser captura todos los conceptos (transporte en columna derecha, etc.)",
                )
            )

        # Líquido = devengado - deducciones
        liquido_calc = nom.total_devengado - nom.total_deducciones
        if abs(liquido_calc - nom.liquido) > _TOLERANCE:
            findings.append(
                self._make_finding(
                    code="D1-002",
                    dimension=dim,
                    severity="critical",
                    confidence=99,
                    title="Líquido no cuadra",
                    description=f"Devengado ({nom.total_devengado:.2f}) - Deducciones ({nom.total_deducciones:.2f}) = {liquido_calc:.2f}, pero el PDF indica líquido {nom.liquido:.2f}",
                    nom=nom,
                    periodo=periodo,
                    expected=liquido_calc,
                    actual=nom.liquido,
                    reference="A. TOTAL DEVENGADO - B. TOTAL A DEDUCIR = LÍQUIDO",
                )
            )

        # Coste empresa = devengado + SS empresa
        if nom.ss_emp_total > 0:
            coste_calc = nom.total_devengado + nom.ss_emp_total
            if abs(coste_calc - nom.coste_total_empresa) > _TOLERANCE:
                findings.append(
                    self._make_finding(
                        code="D1-003",
                        dimension=dim,
                        severity="high",
                        confidence=95,
                        title="Coste empresa no cuadra",
                        description=f"Devengado ({nom.total_devengado:.2f}) + SS emp ({nom.ss_emp_total:.2f}) = {coste_calc:.2f}, pero PDF indica {nom.coste_total_empresa:.2f}",
                        nom=nom,
                        periodo=periodo,
                        expected=coste_calc,
                        actual=nom.coste_total_empresa,
                    )
                )

        # SS trab: base × tasa = importe
        for d in nom.deducciones_ss:
            if d.base > 0 and d.tipo_pct > 0:
                expected_imp = round(d.base * d.tipo_pct / 100, 2)
                if abs(expected_imp - d.importe) > _TOLERANCE:
                    findings.append(
                        self._make_finding(
                            code="D1-004",
                            dimension=dim,
                            severity="medium",
                            confidence=90,
                            title=f"SS trab {d.concepto}: base×tasa != importe",
                            description=f"Base {d.base:.2f} × {d.tipo_pct}% = {expected_imp:.2f}, pero PDF indica {d.importe:.2f}",
                            nom=nom,
                            periodo=periodo,
                            expected=expected_imp,
                            actual=d.importe,
                        )
                    )

        # SS emp: base × tasa = importe
        for a in nom.aportaciones_empresa:
            if a.base > 0 and a.tipo_pct > 0:
                expected_imp = round(a.base * a.tipo_pct / 100, 2)
                if abs(expected_imp - a.importe) > _TOLERANCE:
                    findings.append(
                        self._make_finding(
                            code="D1-005",
                            dimension=dim,
                            severity="medium",
                            confidence=90,
                            title=f"SS emp {a.concepto}: base×tasa != importe",
                            description=f"Base {a.base:.2f} × {a.tipo_pct}% = {expected_imp:.2f}, pero PDF indica {a.importe:.2f}",
                            nom=nom,
                            periodo=periodo,
                            expected=expected_imp,
                            actual=a.importe,
                        )
                    )

        return findings

    # ── D2: Cumplimiento legal SS ──

    def _d2_ss_legal(self, nom: ParsedNomina, periodo: str) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        dim = "D2_ss_legal"

        for d in nom.deducciones_ss:
            expected_rate = SS_TRAB_EXPECTED.get(d.tipo)
            if expected_rate and abs(d.tipo_pct - expected_rate) > 0.01:
                findings.append(
                    self._make_finding(
                        code="D2-001",
                        dimension=dim,
                        severity="critical" if abs(d.tipo_pct - expected_rate) > 0.5 else "high",
                        confidence=95,
                        title=f"Tasa SS trab {d.concepto} incorrecta",
                        description=f"Tasa aplicada: {d.tipo_pct}%. Esperada 2026: {expected_rate}%",
                        nom=nom,
                        periodo=periodo,
                        expected=expected_rate,
                        actual=d.tipo_pct,
                        reference="Orden ISM/31/2026 (BOE-A-2026-1921)",
                    )
                )

        for a in nom.aportaciones_empresa:
            expected_rate = SS_EMP_EXPECTED.get(a.tipo)
            if expected_rate and abs(a.tipo_pct - expected_rate) > 0.01:
                findings.append(
                    self._make_finding(
                        code="D2-002",
                        dimension=dim,
                        severity="high" if a.tipo != "at_ep" else "medium",
                        confidence=85,
                        title=f"Tasa SS emp {a.concepto} inesperada",
                        description=f"Tasa aplicada: {a.tipo_pct}%. Referencia 2026: {expected_rate}%. AT/EP varía por CNAE.",
                        nom=nom,
                        periodo=periodo,
                        expected=expected_rate,
                        actual=a.tipo_pct,
                        reference="Orden ISM/31/2026 + Art.119 LGSS (AT/EP por CNAE)",
                    )
                )

        # Tope de base — con ajuste por jornada parcial
        # Art.147.2 LGSS: la base mínima para jornada parcial es proporcional al
        # coeficiente de parcialidad (horas reales / horas completas).
        base = nom.base_cotizacion_ss
        if base > 0:
            jornada_pct = self._estimate_jornada_pct(nom)
            base_min_proporcional = round(BASE_MIN_2026 * jornada_pct, 2)

            if base < base_min_proporcional - _TOLERANCE:
                if jornada_pct < 1.0:
                    findings.append(
                        self._make_finding(
                            code="D2-003",
                            dimension=dim,
                            severity="high",
                            confidence=75,
                            title="Base SS inferior al mínimo proporcional (jornada parcial)",
                            description=(
                                f"Base: {base:.2f} EUR. Mínimo proporcional ({jornada_pct:.0%}): "
                                f"{base_min_proporcional:.2f} EUR. "
                                f"Base mínima completa 2026: {BASE_MIN_2026:.2f} EUR."
                            ),
                            nom=nom,
                            periodo=periodo,
                            expected=base_min_proporcional,
                            actual=base,
                            reference="Art.147.2 LGSS + Orden ISM/31/2026 — base mínima proporcional jornada parcial",
                            fix="Verificar coeficiente de parcialidad y bases de cotización",
                        )
                    )
                else:
                    findings.append(
                        self._make_finding(
                            code="D2-003",
                            dimension=dim,
                            severity="critical",
                            confidence=90,
                            title="Base cotización SS inferior al mínimo 2026",
                            description=f"Base: {base:.2f} EUR. Mínimo legal 2026: {BASE_MIN_2026:.2f} EUR",
                            nom=nom,
                            periodo=periodo,
                            expected=BASE_MIN_2026,
                            actual=base,
                            reference="Orden ISM/31/2026 — base mínima mensual",
                        )
                    )
            if base > BASE_MAX_2026 + _TOLERANCE:
                findings.append(
                    self._make_finding(
                        code="D2-004",
                        dimension=dim,
                        severity="high",
                        confidence=90,
                        title="Base cotización SS superior al máximo 2026",
                        description=f"Base: {base:.2f} EUR. Máximo legal 2026: {BASE_MAX_2026:.2f} EUR",
                        nom=nom,
                        periodo=periodo,
                        expected=BASE_MAX_2026,
                        actual=base,
                        reference="Orden ISM/31/2026 — base máxima mensual",
                    )
                )

        return findings

    @staticmethod
    def _estimate_jornada_pct(nom: ParsedNomina) -> float:
        """Estima el coeficiente de jornada parcial comparando base SS con SMI.

        Art.147.2 LGSS: en contratos a tiempo parcial, la base mínima de cotización
        se reduce proporcionalmente al coeficiente de parcialidad.

        Heurística: si la base de cotización está por debajo de la base mínima
        completa, el coeficiente es base / base_mínima (aproximación conservadora).
        Si la base ≥ base mínima, se asume jornada completa (1.0).
        """
        if base := nom.base_cotizacion_ss:
            if base < BASE_MIN_2026 - _TOLERANCE:
                return min(base / BASE_MIN_2026, 1.0)
        return 1.0

    # ── D3: IRPF razonabilidad ──

    def _d3_irpf(self, nom: ParsedNomina, periodo: str) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        dim = "D3_irpf"

        if nom.irpf_base > 0 and nom.total_devengado > 0:
            if abs(nom.irpf_base - nom.total_devengado) > _TOLERANCE:
                findings.append(
                    self._make_finding(
                        code="D3-001",
                        dimension=dim,
                        severity="medium",
                        confidence=70,
                        title="Base IRPF != Total devengado",
                        description=f"Base IRPF: {nom.irpf_base:.2f}. Total devengado: {nom.total_devengado:.2f}. Deberían coincidir en nóminas estándar.",
                        nom=nom,
                        periodo=periodo,
                        expected=nom.total_devengado,
                        actual=nom.irpf_base,
                        reference="Art.80 RIRPF — base de retención",
                    )
                )

        if nom.irpf_base > 0 and nom.irpf_pct > 0:
            irpf_calc = round(nom.irpf_base * nom.irpf_pct / 100, 2)
            if abs(irpf_calc - nom.irpf_importe) > _TOLERANCE:
                findings.append(
                    self._make_finding(
                        code="D3-002",
                        dimension=dim,
                        severity="high",
                        confidence=85,
                        title="Importe IRPF no cuadra con base × %",
                        description=f"Base {nom.irpf_base:.2f} × {nom.irpf_pct}% = {irpf_calc:.2f}, pero PDF indica {nom.irpf_importe:.2f}",
                        nom=nom,
                        periodo=periodo,
                        expected=irpf_calc,
                        actual=nom.irpf_importe,
                    )
                )

        return findings

    # ── D4: Cumplimiento convenio ──

    def _d4_convenio(self, nom: ParsedNomina, periodo: str) -> list[AuditFinding]:
        if not self.convenio_data:
            return []

        findings: list[AuditFinding] = []
        dim = "D4_convenio"

        cat_data = self._find_category_data(nom.grupo_profesional)

        if not cat_data:
            findings.append(
                self._make_finding(
                    code="D4-001",
                    dimension=dim,
                    severity="medium",
                    confidence=80,
                    title=f"Categoría '{nom.grupo_profesional}' no existe en convenio",
                    description=f"El grupo profesional '{nom.grupo_profesional}' no aparece en el anexo salarial del convenio. Verificar si es correcto o si debe reasignarse.",
                    nom=nom,
                    periodo=periodo,
                    reference="Anexo I del convenio colectivo",
                    fix="Reasignar a la categoría correcta del convenio",
                )
            )
            return findings

        salario_minimo = (
            cat_data.get("monthly_14_payments_eur")
            or cat_data.get("monthly_15_payments_eur")
            or 0.0
        )
        if salario_minimo == 0 and cat_data.get("annual_eur"):
            pagas = 14
            resumen = self.convenio_data.get("resumen_operativo", {})
            pagas += resumen.get("pagas_extras", 2)
            salario_minimo = round(cat_data["annual_eur"] / pagas, 2)

        if salario_minimo > 0:
            salario_base = self._get_devengo_by_tipo(nom, "salario_base")
            if salario_base < salario_minimo - _TOLERANCE:
                gap = salario_minimo - salario_base
                findings.append(
                    self._make_finding(
                        code="D4-002",
                        dimension=dim,
                        severity="critical",
                        confidence=95,
                        title=f"Salario base inferior al mínimo convenio",
                        description=f"Salario base: {salario_base:.2f} EUR. Mínimo convenio para '{nom.grupo_profesional}': {salario_minimo:.2f} EUR. Déficit: {gap:.2f} EUR/mes.",
                        nom=nom,
                        periodo=periodo,
                        expected=salario_minimo,
                        actual=salario_base,
                        deviation=gap,
                        reference=f"Art.30 y Anexo I del convenio — categoría '{nom.grupo_profesional}'",
                        fix=f"Ajustar salario base a {salario_minimo:.2f} EUR como mínimo",
                    )
                )

        # Plus transporte
        if self._plus_transporte > 0:
            transporte = self._get_devengo_by_tipo(nom, "transporte")
            if transporte <= 0:
                findings.append(
                    self._make_finding(
                        code="D4-003",
                        dimension=dim,
                        severity="high",
                        confidence=85,
                        title="Plus transporte ausente",
                        description=f"El convenio establece un plus de transporte de {self._plus_transporte:.2f} EUR, pero la nómina no lo incluye.",
                        nom=nom,
                        periodo=periodo,
                        expected=self._plus_transporte,
                        actual=0.0,
                        reference="Art.33 del convenio — plus transporte",
                        fix=f"Incluir plus transporte de {self._plus_transporte:.2f} EUR",
                    )
                )
            elif abs(transporte - self._plus_transporte) > _TOLERANCE:
                findings.append(
                    self._make_finding(
                        code="D4-004",
                        dimension=dim,
                        severity="medium",
                        confidence=75,
                        title="Plus transporte no coincide con convenio",
                        description=f"Transporte nómina: {transporte:.2f} EUR. Convenio: {self._plus_transporte:.2f} EUR",
                        nom=nom,
                        periodo=periodo,
                        expected=self._plus_transporte,
                        actual=transporte,
                        reference="Art.33 del convenio",
                    )
                )

        return findings

    # ── D5: Coherencia inter-trabajador ──

    def _d5_inter_worker(self, nominas: list[ParsedNomina], periodo: str) -> list[AuditFinding]:
        if len(nominas) < 2:
            return []

        findings: list[AuditFinding] = []
        dim = "D5_inter_worker"

        by_grupo: dict[str, list[ParsedNomina]] = {}
        for nom in nominas:
            key = nom.grupo_profesional
            by_grupo.setdefault(key, []).append(nom)

        for grupo, workers in by_grupo.items():
            if len(workers) < 2:
                continue
            bases = [self._get_devengo_by_tipo(w, "salario_base") for w in workers]
            avg_base = sum(bases) / len(bases)
            for w, base in zip(workers, bases):
                if base > 0 and avg_base > 0 and abs(base - avg_base) / avg_base > 0.5:
                    findings.append(
                        self._make_finding(
                            code="D5-001",
                            dimension=dim,
                            severity="medium",
                            confidence=60,
                            title=f"Salario base outlier en categoría '{grupo}'",
                            description=f"{w.nombre_trabajador}: {base:.2f} EUR. Media del grupo: {avg_base:.2f} EUR. Desviación >50%.",
                            nom=w,
                            periodo=periodo,
                            expected=avg_base,
                            actual=base,
                        )
                    )

        return findings

    # ── D6: Consistencia temporal ──

    def _d6_temporal(
        self, nom: ParsedNomina, prev: ParsedNomina, periodo: str
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        dim = "D6_temporal"

        curr_base = self._get_devengo_by_tipo(nom, "salario_base")
        prev_base = self._get_devengo_by_tipo(prev, "salario_base")

        if curr_base > 0 and prev_base > 0 and abs(curr_base - prev_base) > _TOLERANCE:
            diff = curr_base - prev_base
            findings.append(
                self._make_finding(
                    code="D6-001",
                    dimension=dim,
                    severity="medium",
                    confidence=70,
                    title="Salario base cambió entre meses",
                    description=f"Mes anterior: {prev_base:.2f} EUR. Mes actual: {curr_base:.2f} EUR. Cambio: {diff:+.2f} EUR.",
                    nom=nom,
                    periodo=periodo,
                    expected=prev_base,
                    actual=curr_base,
                    deviation=diff,
                    reference="Art.30 convenio — revisión salarial anual",
                    fix="Verificar si el cambio se debe a revisión salarial, categoría o error",
                )
            )

        if nom.base_cotizacion_ss > 0 and prev.base_cotizacion_ss > 0:
            ss_diff = abs(nom.base_cotizacion_ss - prev.base_cotizacion_ss)
            if ss_diff > prev.base_cotizacion_ss * 0.1:
                findings.append(
                    self._make_finding(
                        code="D6-002",
                        dimension=dim,
                        severity="low",
                        confidence=50,
                        title="Base SS varió >10% entre meses",
                        description=f"Anterior: {prev.base_cotizacion_ss:.2f}. Actual: {nom.base_cotizacion_ss:.2f}",
                        nom=nom,
                        periodo=periodo,
                        expected=prev.base_cotizacion_ss,
                        actual=nom.base_cotizacion_ss,
                    )
                )

        curr_types = {d.tipo for d in nom.devengos}
        prev_types = {d.tipo for d in prev.devengos}
        new_types = curr_types - prev_types
        if new_types:
            findings.append(
                self._make_finding(
                    code="D6-003",
                    dimension=dim,
                    severity="low",
                    confidence=60,
                    title="Nuevos conceptos de devengo",
                    description=f"Conceptos nuevos respecto al mes anterior: {', '.join(new_types)}",
                    nom=nom,
                    periodo=periodo,
                )
            )

        return findings

    # ── D7: Embargos y retenciones (LEC art.607) ──

    # Art.607.1 LEC: inembargable = 1×SMI (NO 2×SMI).
    # Art.607.2 LEC: graduated tramos:
    #   Tramo 0: 0 a 1 SMI         →  0% (inembargable)
    #   Tramo 1: 1 SMI a 2 SMI     → 30%
    #   Tramo 2: 2 SMI a 3 SMI     → 50%
    #   Tramo 3: 3 SMI a 4 SMI     → 60%
    #   Tramo 4: 4 SMI a 5 SMI     → 75%
    #   Tramo 5: > 5 SMI           → 90%
    # DGT CV 14/09/20: SMI íntegro (sin prorratear por jornada parcial).
    # TSJ País Vasco 03/05/16 EDJ 131883: si pagas prorreadas (12),
    #   SMI referencia = SMI × 14/12.

    _TRAMOS_EMBARGO: list[tuple[int, float]] = [
        (1, 0.00),  # hasta 1 SMI: inembargable
        (2, 0.30),  # de 1 a 2 SMI
        (3, 0.50),  # de 2 a 3 SMI
        (4, 0.60),  # de 3 a 4 SMI
        (5, 0.75),  # de 4 a 5 SMI
        (999, 0.90),  # > 5 SMI
    ]

    def _d7_embargos(self, nom: ParsedNomina, periodo: str) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        dim = "D7_embargos"

        for emb in nom.embargos:
            embargo_imp = emb.get("importe", 0.0)
            if embargo_imp <= 0:
                continue

            neto_previo = nom.liquido + embargo_imp
            if neto_previo <= 0:
                continue

            # SMI prorrateado si el trabajador tiene pagas extras prorreadas (12 pagas)
            smi_ref = SMI_MENSUAL_2026 * 14 / 12  # 1.424,50 en 2026
            # Si tiene devengos de tipo prorrata_extra, confirma que son 12 pagas
            has_prorrata = any(d.tipo == "prorrata_extra" for d in nom.devengos)
            if not has_prorrata:
                smi_ref = SMI_MENSUAL_2026  # 1.221 en 14 pagas

            # Art.607.1: salario ≤ 1×SMI → inembargable
            if neto_previo <= smi_ref:
                findings.append(
                    self._make_finding(
                        code="D7-001",
                        dimension=dim,
                        severity="critical",
                        confidence=95,
                        title="Embargo sobre salario inembargable",
                        description=(
                            f"Neto previo al embargo ({neto_previo:.2f} EUR) ≤ SMI referencia "
                            f"({smi_ref:.2f} EUR). El salario es inembargable según LEC art.607.1."
                        ),
                        nom=nom,
                        periodo=periodo,
                        expected=0.0,
                        actual=embargo_imp,
                        reference="Art.607.1 LEC — salarios inembargables",
                    )
                )
                continue

            max_embargable = self._calc_max_embargo(neto_previo, smi_ref)
            if embargo_imp > max_embargable + _TOLERANCE:
                findings.append(
                    self._make_finding(
                        code="D7-002",
                        dimension=dim,
                        severity="high",
                        confidence=85,
                        title="Embargo excede límite legal LEC art.607",
                        description=(
                            f"Embargo: {embargo_imp:.2f} EUR. Máximo legal por tramos "
                            f"art.607.2: {max_embargable:.2f} EUR. "
                            f"Neto previo: {neto_previo:.2f} EUR, SMI ref: {smi_ref:.2f} EUR."
                        ),
                        nom=nom,
                        periodo=periodo,
                        expected=max_embargable,
                        actual=embargo_imp,
                        deviation=round(embargo_imp - max_embargable, 2),
                        reference="Art.607.2 LEC — escala gradual de embargos",
                    )
                )

        return findings

    @classmethod
    def _calc_max_embargo(cls, neto: float, smi: float) -> float:
        """Calcula el embargo máximo según la escala del art.607.2 LEC.

        Cada porcentaje se aplica SOLO al tramo correspondiente (como el IRPF).
        """
        total = 0.0
        limite_inf = smi  # el primer tramo empieza en 1×SMI

        for multiplicador, pct in cls._TRAMOS_EMBARGO:
            if multiplicador <= 1:
                continue  # tramo inembargable

            limite_sup = smi * multiplicador
            if neto <= limite_inf:
                break

            base_tramo = min(neto, limite_sup) - limite_inf
            if base_tramo <= 0:
                break

            total += base_tramo * pct
            limite_inf = limite_sup

        return round(total, 2)

    # ── Helpers ──

    @staticmethod
    def _make_finding(
        code: str,
        dimension: str,
        severity: str,
        confidence: int,
        title: str,
        description: str,
        nom: ParsedNomina,
        periodo: str,
        expected: float | None = None,
        actual: float | None = None,
        deviation: float | None = None,
        reference: str = "",
        fix: str = "",
    ) -> AuditFinding:
        if deviation is None and expected is not None and actual is not None:
            deviation = round(actual - expected, 2)
        return AuditFinding(
            code=code,
            dimension=dimension,
            severity=severity,
            confidence=confidence,
            title=title,
            description=description,
            worker_name=nom.nombre_trabajador,
            period=periodo,
            expected_value=expected,
            actual_value=actual,
            deviation=deviation,
            reference=reference,
            fix_suggestion=fix,
        )

    def _find_category_data(self, grupo_profesional: str) -> dict[str, Any] | None:
        cleaned = grupo_profesional.rstrip(".")
        data = self._salarios_por_categoria.get(cleaned)
        if data:
            return data
        for cat, d in self._salarios_por_categoria.items():
            if cat.rstrip(".") == cleaned:
                return d
        # Fuzzy: Sage/A3 abbreviates categories ("AUXILIAR ADMINIS" → "Auxiliar Administrativo",
        # "MAQUINISTA" → "Ayudante de maquinista")
        cleaned_lower = cleaned.lower()
        for cat, d in self._salarios_por_categoria.items():
            cat_clean = cat.rstrip(".").lower()
            if cleaned_lower in cat_clean or cat_clean in cleaned_lower:
                return d
        return None

    @staticmethod
    def _get_devengo_by_tipo(nom: ParsedNomina, tipo: str) -> float:
        return sum(d.importe for d in nom.devengos if d.tipo == tipo)

    @staticmethod
    def _compute_summary(report: AuditReport) -> dict[str, int]:
        counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for w in report.workers:
            for f in w.findings:
                sev = f.severity.lower()
                if sev in counts:
                    counts[sev] += 1
        for f in report.findings:
            sev = f.severity.lower()
            if sev in counts:
                counts[sev] += 1
        return counts
