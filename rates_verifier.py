"""Verificador completo de datos normativos via Perplexity API.

Verifica contra fuentes reales en internet:
  1. Tasas SS 2026 (Orden de Cotización)
  2. IRPF 2026 — tramos estatales y reducción rendimientos trabajo
  3. SMI 2026 — Salario Mínimo Interprofesional
  4. Revisión salarial convenios (acuáticas, oficinas)

IMPORTANTE: Todo es ORIENTATIVO. Nunca bloquea operaciones.
Graceful degradation si no hay PERPLEXITY_API_KEY.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from typing import Any

_PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
_TIMEOUT = 35
_CACHE_TTL = 86400  # 24h


# ======================================================================
# Nuestros valores hardcoded — referencia para comparar
# ======================================================================

_OUR_SS_2026 = {
    "empresa_cc": 23.60,
    "empresa_desempleo_indefinido": 5.50,
    "empresa_desempleo_temporal": 6.70,
    "empresa_fogasa": 0.20,
    "empresa_fp": 0.60,
    "empresa_mei": 0.75,  # RDL 3/2026 — actualizado 2026-03-22
    "trab_cc": 4.70,
    "trab_desempleo_indefinido": 1.55,
    "trab_desempleo_temporal": 1.60,
    "trab_fp": 0.10,
    "trab_mei": 0.15,  # RDL 3/2026 — actualizado 2026-03-22
    "base_min_mensual": 1424.50,  # Orden PJC/297/2026 — actualizado 2026-03-22
    "base_max_mensual": 5101.20,  # Orden PJC/297/2026 — actualizado 2026-03-22
}

# Tramos estatales IRPF que tenemos (límite superior, tipo)
_OUR_IRPF_STATE_2026 = [
    {"hasta": 12450.0, "tipo_pct": 9.5},
    {"hasta": 20200.0, "tipo_pct": 12.0},
    {"hasta": 35200.0, "tipo_pct": 15.0},
    {"hasta": 60000.0, "tipo_pct": 18.5},
    {"hasta": 300000.0, "tipo_pct": 22.5},
    {"hasta": None, "tipo_pct": 24.5},  # resto
]
_OUR_IRPF_REDUCCION = {
    "importe_maximo": 7302.0,
    "limite_inferior": 14852.0,
    "limite_superior": 17673.52,
    "importe_minimo": 2364.34,
}

# SMI que usamos internamente como referencia
_OUR_SMI_2026_MENSUAL = 1221.0  # RD 126/2026 de 18 febrero — actualizado 2026-03-22

# Datos de convenios para verificar revisión salarial
_CONVENIOS_A_VERIFICAR = [
    {
        "id": "convenio_acuaticas_2025_2027",
        "nombre": "Convenio colectivo estatal de mantenimiento y conservación de instalaciones acuáticas",
        "vigencia_desde": 2025,
        "vigencia_hasta": 2027,
        "sector": "mantenimiento piscinas instalaciones acuáticas",
        "ambito": "estatal",
        "nuestro_salario_base_minimo": 1400.0,  # aprox. del convenio subido
    },
    {
        "id": "convenio_oficinas_despachos_alicante_2024_2026",
        "nombre": "Convenio colectivo de Oficinas y Despachos de Alicante",
        "vigencia_desde": 2024,
        "vigencia_hasta": 2026,
        "sector": "oficinas y despachos",
        "ambito": "Alicante",
        "nuestro_salario_base_minimo": 1300.0,  # aprox.
    },
]

_SS_TOLERANCE = 0.05  # pp
_BASE_TOLERANCE_PCT = 0.005  # 0.5% para bases en €
_IRPF_TOLERANCE = 0.5  # pp (tolerancia mayor — CC.AA. varían)
_SMI_TOLERANCE_PCT = 0.02  # 2% para SMI


# ======================================================================
# Dataclasses
# ======================================================================


@dataclass
class CheckResult:
    """Resultado de un check individual."""

    check: str  # identificador: "ss" | "irpf" | "smi" | "convenio_xxx"
    label: str  # nombre legible
    status: str  # "ok" | "warning" | "uncertain" | "unavailable" | "error"
    message: str
    discrepancies: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    perplexity_data: dict[str, Any] = field(default_factory=dict)
    verified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "label": self.label,
            "status": self.status,
            "message": self.message,
            "discrepancies": self.discrepancies,
            "sources": self.sources,
            "verified_at": self.verified_at,
        }


@dataclass
class FullVerificationResult:
    """Resultado combinado de todos los checks."""

    overall_status: str  # peor status entre todos los checks
    checks: list[CheckResult]
    verified_at: str
    is_advisory: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "is_advisory": self.is_advisory,
            "verified_at": self.verified_at,
            "checks": [c.to_dict() for c in self.checks],
            "our_reference": {
                "ss_2026": _OUR_SS_2026,
                "irpf_estatal_tramos": _OUR_IRPF_STATE_2026,
                "irpf_reduccion": _OUR_IRPF_REDUCCION,
                "smi_2026_mensual": _OUR_SMI_2026_MENSUAL,
            },
        }


# ======================================================================
# Clase principal
# ======================================================================


class RatesVerifier:
    """Verifica SS, IRPF, SMI y convenios contra fuentes reales via Perplexity."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("PERPLEXITY_API_KEY", "")
        self._cache: dict[str, Any] = {}
        self._cache_ts: float = 0.0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Punto de entrada principal
    # ------------------------------------------------------------------

    def verify_all(self, force: bool = False) -> FullVerificationResult:
        """Ejecuta todos los checks y devuelve resultado combinado."""
        today = date.today().isoformat()

        if not self.available:
            unavailable = CheckResult(
                check="all",
                label="Verificación completa",
                status="unavailable",
                message="PERPLEXITY_API_KEY no configurada. Configúrala en Dokploy para activar la verificación automática.",
                verified_at=today,
            )
            return FullVerificationResult(
                overall_status="unavailable",
                checks=[unavailable],
                verified_at=today,
            )

        # Cache check
        if not force and self._cache and (time.time() - self._cache_ts) < _CACHE_TTL:
            return FullVerificationResult(**self._cache)

        # Ejecutar los 4 checks (en serie — la API de Perplexity no admite concurrencia)
        checks: list[CheckResult] = []
        checks.append(self._check_ss())
        checks.append(self._check_smi())
        checks.append(self._check_irpf())
        for conv in _CONVENIOS_A_VERIFICAR:
            checks.append(self._check_convenio(conv))

        # Overall status: el peor de todos
        priority = ["error", "warning", "uncertain", "unavailable", "ok"]
        statuses = [c.status for c in checks]
        overall = "ok"
        for p in priority:
            if p in statuses:
                overall = p
                break

        result = FullVerificationResult(
            overall_status=overall,
            checks=checks,
            verified_at=today,
        )

        # Guardar en caché
        self._cache = {
            "overall_status": result.overall_status,
            "checks": result.checks,
            "verified_at": result.verified_at,
        }
        self._cache_ts = time.time()
        return result

    # Mantener compatibilidad con código anterior
    def verify_ss_rates(self, force: bool = False) -> Any:
        """Compatibilidad hacia atrás — llama a verify_all()."""
        result = self.verify_all(force=force)
        ss = next((c for c in result.checks if c.check == "ss"), None)
        if ss is None:
            return _unavailable_compat()

        class _Compat:
            def __init__(self, c: CheckResult) -> None:
                self.status = c.status
                self.message = c.message
                self.discrepancies = c.discrepancies
                self.sources = c.sources
                self.verified_at = c.verified_at
                self.is_advisory = True

            def to_dict(self) -> dict:
                return {
                    "status": self.status,
                    "message": self.message,
                    "discrepancies": self.discrepancies,
                    "sources": self.sources,
                    "verified_at": self.verified_at,
                    "is_advisory": True,
                    "our_rates": _OUR_SS_2026,
                }

        return _Compat(ss)

    # ------------------------------------------------------------------
    # CHECK 1 — Tasas SS
    # ------------------------------------------------------------------

    def _check_ss(self) -> CheckResult:
        label = "Tasas SS 2026 (Orden de Cotización)"
        prompt = """Busca las tasas de cotización a la Seguridad Social española para el año 2026 (Régimen General).
Fuentes: BOE, Ministerio de Inclusión y Seguridad Social, Orden de Cotización 2026.

Responde SOLO con JSON:
{
  "empresa_cc": <% contingencias comunes empresa>,
  "empresa_desempleo_indefinido": <% desempleo indefinido empresa>,
  "empresa_desempleo_temporal": <% desempleo temporal empresa>,
  "empresa_fogasa": <% FOGASA>,
  "empresa_fp": <% Formación Profesional empresa>,
  "empresa_mei": <% MEI empresa>,
  "trab_cc": <% contingencias comunes trabajador>,
  "trab_desempleo_indefinido": <% desempleo indefinido trabajador>,
  "trab_desempleo_temporal": <% desempleo temporal trabajador>,
  "trab_fp": <% FP trabajador>,
  "trab_mei": <% MEI trabajador>,
  "base_min_mensual": <euros>,
  "base_max_mensual": <euros>,
  "fuente": "<URL o referencia BOE>",
  "confianza": "alta"|"media"|"baja"
}

Nuestros valores actuales: empresa CC=23.60%, trab CC=4.70%, base min=1323€, base max=4720.50€
Si no encuentras datos fiables de 2026 específicamente, pon "confianza":"baja" y los campos como null."""

        return self._run_check("ss", label, prompt, self._parse_ss)

    def _parse_ss(self, data: dict, label: str) -> CheckResult:
        today = date.today().isoformat()
        confianza = data.get("confianza", "baja")
        sources = [s for s in [data.get("fuente", "")] if s]

        if confianza == "baja":
            return CheckResult(
                "ss",
                label,
                "uncertain",
                "❓ Perplexity no encontró datos SS 2026 con certeza. Revisa la Orden de Cotización en BOE.",
                sources=sources,
                verified_at=today,
            )

        fields = [
            ("empresa_cc", "Empresa — Contingencias Comunes (%)"),
            ("empresa_desempleo_indefinido", "Empresa — Desempleo indefinido (%)"),
            ("empresa_desempleo_temporal", "Empresa — Desempleo temporal (%)"),
            ("empresa_fogasa", "Empresa — FOGASA (%)"),
            ("empresa_fp", "Empresa — Formación Profesional (%)"),
            ("empresa_mei", "Empresa — MEI (%)"),
            ("trab_cc", "Trabajador — Contingencias Comunes (%)"),
            ("trab_desempleo_indefinido", "Trabajador — Desempleo indefinido (%)"),
            ("trab_desempleo_temporal", "Trabajador — Desempleo temporal (%)"),
            ("trab_fp", "Trabajador — FP (%)"),
            ("trab_mei", "Trabajador — MEI (%)"),
            ("base_min_mensual", "Base mínima mensual (€)"),
            ("base_max_mensual", "Base máxima mensual (€)"),
        ]
        discs = []
        for key, lbl in fields:
            their = data.get(key)
            ours = _OUR_SS_2026.get(key)
            if their is None or ours is None:
                continue
            tol = ours * _BASE_TOLERANCE_PCT if "base_" in key else _SS_TOLERANCE
            diff = abs(float(their) - float(ours))
            if diff > tol:
                discs.append(
                    {
                        "label": lbl,
                        "nuestro": ours,
                        "perplexity": float(their),
                        "diferencia": round(diff, 4),
                    }
                )

        if discs:
            return CheckResult(
                "ss",
                label,
                "warning",
                f"⚠️ {len(discs)} diferencia(s) detectada(s) en tasas SS. Revisa con la Orden de Cotización oficial.",
                discrepancies=discs,
                sources=sources,
                verified_at=today,
            )
        return CheckResult(
            "ss",
            label,
            "ok",
            "✅ Tasas SS 2026 confirmadas correctas.",
            sources=sources,
            verified_at=today,
        )

    # ------------------------------------------------------------------
    # CHECK 2 — SMI
    # ------------------------------------------------------------------

    def _check_smi(self) -> CheckResult:
        label = "SMI 2026 (Salario Mínimo Interprofesional)"
        prompt = f"""¿Cuál es el Salario Mínimo Interprofesional (SMI) vigente en España en 2026?
Busca en BOE, Real Decreto de SMI 2026.

Responde SOLO con JSON:
{{
  "smi_mensual_eur": <importe mensual bruto en euros, 14 pagas>,
  "smi_diario_eur": <importe diario>,
  "aprobado_por": "<Real Decreto o referencia normativa>",
  "fecha_aprobacion": "<fecha o año>",
  "fuente": "<URL o referencia BOE>",
  "confianza": "alta"|"media"|"baja"
}}

Nuestro valor de referencia: {_OUR_SMI_2026_MENSUAL}€/mes (puede estar desactualizado).
Si el SMI 2026 aún no está aprobado, indica el vigente y pon "confianza":"media"."""

        return self._run_check("smi", label, prompt, self._parse_smi)

    def _parse_smi(self, data: dict, label: str) -> CheckResult:
        today = date.today().isoformat()
        confianza = data.get("confianza", "baja")
        sources = [s for s in [data.get("fuente", "")] if s]
        their_smi = data.get("smi_mensual_eur")

        if confianza == "baja" or their_smi is None:
            return CheckResult(
                "smi",
                label,
                "uncertain",
                "❓ No se encontró el SMI 2026 con certeza. Verifica en BOE.",
                sources=sources,
                verified_at=today,
            )

        try:
            their_smi = float(their_smi)
        except (ValueError, TypeError):
            return CheckResult(
                "smi", label, "uncertain", "❓ Respuesta SMI no interpretable.", verified_at=today
            )

        diff = abs(their_smi - _OUR_SMI_2026_MENSUAL)
        tol = _OUR_SMI_2026_MENSUAL * _SMI_TOLERANCE_PCT

        norma = data.get("aprobado_por", "")
        msg_extra = f" ({norma})" if norma else ""

        if diff > tol:
            discs = [
                {
                    "label": "SMI mensual (€/mes, 14 pagas)",
                    "nuestro": _OUR_SMI_2026_MENSUAL,
                    "perplexity": their_smi,
                    "diferencia": round(diff, 2),
                }
            ]
            return CheckResult(
                "smi",
                label,
                "warning",
                f"⚠️ SMI 2026 detectado: {their_smi:.2f}€/mes{msg_extra}. Nuestro valor: {_OUR_SMI_2026_MENSUAL:.2f}€. "
                "Actualizar si hay diferencia significativa.",
                discrepancies=discs,
                sources=sources,
                verified_at=today,
            )

        return CheckResult(
            "smi",
            label,
            "ok",
            f"✅ SMI 2026 confirmado: {their_smi:.2f}€/mes{msg_extra}.",
            sources=sources,
            verified_at=today,
        )

    # ------------------------------------------------------------------
    # CHECK 3 — IRPF
    # ------------------------------------------------------------------

    def _check_irpf(self) -> CheckResult:
        label = "IRPF 2026 — Tramos estatales y reducción"
        our_tramos = "; ".join(
            f"hasta {t['hasta']:,.0f}€ → {t['tipo_pct']}%"
            if t["hasta"]
            else f"resto → {t['tipo_pct']}%"
            for t in _OUR_IRPF_STATE_2026
        )
        prompt = f"""¿Cuáles son los tramos del IRPF estatal vigentes en España para 2026?
También necesito la reducción por rendimientos del trabajo (Art. 20 LIRPF).
Fuentes: AEAT, Ley 35/2006 LIRPF, Presupuestos Generales del Estado 2026 o última normativa vigente.

Responde SOLO con JSON:
{{
  "tramos_estatales": [
    {{"hasta_eur": <límite o null si es el último tramo>, "tipo_pct": <tipo aplicado a ese tramo>}},
    ...
  ],
  "reduccion_rendimientos_trabajo": {{
    "importe_maximo": <reducción máxima en euros>,
    "limite_inferior_eur": <renta hasta la que se aplica el máximo>,
    "limite_superior_eur": <renta a partir de la que se aplica el mínimo>,
    "importe_minimo": <reducción mínima en euros>
  }},
  "anio_fiscal": 2026,
  "normativa": "<referencia legal>",
  "fuente": "<URL o referencia>",
  "confianza": "alta"|"media"|"baja"
}}

Nuestros tramos actuales (estatal): {our_tramos}
Nuestra reducción: máximo {_OUR_IRPF_REDUCCION["importe_maximo"]}€ (rentas ≤{_OUR_IRPF_REDUCCION["limite_inferior"]}€), mínimo {_OUR_IRPF_REDUCCION["importe_minimo"]}€ (rentas >{_OUR_IRPF_REDUCCION["limite_superior"]}€)

Si los Presupuestos 2026 no se han aprobado y siguen vigentes los de años anteriores, indícalo."""

        return self._run_check("irpf", label, prompt, self._parse_irpf)

    def _parse_irpf(self, data: dict, label: str) -> CheckResult:
        today = date.today().isoformat()
        confianza = data.get("confianza", "baja")
        sources = [s for s in [data.get("fuente", data.get("normativa", ""))] if s]
        discs = []

        if confianza == "baja":
            return CheckResult(
                "irpf",
                label,
                "uncertain",
                "❓ IRPF 2026: no se encontraron datos fiables. Si los PGE no se han aprobado, "
                "los tramos de 2025 siguen vigentes. Verifica en AEAT.",
                sources=sources,
                verified_at=today,
            )

        # Comparar tramos estatales
        their_tramos = data.get("tramos_estatales", [])
        if their_tramos and len(their_tramos) == len(_OUR_IRPF_STATE_2026):
            for i, (ours, theirs) in enumerate(zip(_OUR_IRPF_STATE_2026, their_tramos)):
                their_tipo = theirs.get("tipo_pct")
                if their_tipo is None:
                    continue
                diff = abs(float(their_tipo) - ours["tipo_pct"])
                if diff > _IRPF_TOLERANCE:
                    limite_label = f"≤{ours['hasta']:,.0f}€" if ours["hasta"] else "resto"
                    discs.append(
                        {
                            "label": f"Tramo IRPF estatal {limite_label}",
                            "nuestro": f"{ours['tipo_pct']}%",
                            "perplexity": f"{their_tipo}%",
                            "diferencia": f"{diff:.2f} pp",
                        }
                    )

        # Comparar reducción rendimientos del trabajo
        their_red = data.get("reduccion_rendimientos_trabajo", {})
        if their_red:
            for key, our_key, lbl in [
                ("importe_maximo", "importe_maximo", "Reducción máxima (€)"),
                ("limite_inferior_eur", "limite_inferior", "Límite inferior reducción (€)"),
            ]:
                their_val = their_red.get(key)
                our_val = _OUR_IRPF_REDUCCION.get(our_key)
                if their_val and our_val:
                    diff = abs(float(their_val) - float(our_val))
                    if diff > our_val * 0.01:  # >1% diferencia
                        discs.append(
                            {
                                "label": lbl,
                                "nuestro": our_val,
                                "perplexity": float(their_val),
                                "diferencia": round(diff, 2),
                            }
                        )

        normativa = data.get("normativa", "")
        nota_pge = ""
        if "prórroga" in (normativa + data.get("fuente", "")).lower() or confianza == "media":
            nota_pge = " (PGE 2026 prorrogados — tramos de 2025 en vigor)"

        if discs:
            return CheckResult(
                "irpf",
                label,
                "warning",
                f"⚠️ {len(discs)} diferencia(s) en tramos IRPF 2026. Verifica en AEAT.{nota_pge}",
                discrepancies=discs,
                sources=sources,
                verified_at=today,
            )

        return CheckResult(
            "irpf",
            label,
            "ok",
            f"✅ Tramos IRPF 2026 confirmados correctos.{nota_pge}",
            sources=sources,
            verified_at=today,
        )

    # ------------------------------------------------------------------
    # CHECK 4 — Revisión salarial de convenio
    # ------------------------------------------------------------------

    def _check_convenio(self, conv: dict) -> CheckResult:
        check_id = f"convenio_{conv['id']}"
        label = f"Revisión salarial — {conv['nombre'][:50]}"
        anio = date.today().year
        prompt = f"""Necesito verificar si hay revisión salarial para {anio} en el siguiente convenio colectivo español:

Nombre: {conv["nombre"]}
Ámbito: {conv["ambito"]}
Sector: {conv["sector"]}
Vigencia: {conv["vigencia_desde"]}–{conv["vigencia_hasta"]}

Preguntas concretas:
1. ¿Qué incremento salarial está pactado para {anio} en este convenio?
2. ¿Se ha publicado en BOE la tabla salarial actualizada para {anio}?
3. ¿Ha habido cláusula de revisión por IPC u otra?

Responde SOLO con JSON:
{{
  "convenio_encontrado": true|false,
  "incremento_pactado_pct": <porcentaje de subida para {anio} o null>,
  "tabla_publicada_boe": true|false|null,
  "clausula_revision_ipc": <descripción breve o null>,
  "salario_base_minimo_actualizado": <importe en euros o null>,
  "notas": "<observaciones importantes>",
  "fuente": "<URL BOE o referencia>",
  "confianza": "alta"|"media"|"baja"
}}

Nuestro salario base mínimo registrado: {conv["nuestro_salario_base_minimo"]}€/mes aprox."""

        return self._run_check(check_id, label, prompt, self._parse_convenio_rev)

    def _parse_convenio_rev(self, data: dict, label: str) -> CheckResult:
        today = date.today().isoformat()
        confianza = data.get("confianza", "baja")
        check_id = "convenio"  # sobreescrito por _run_check
        sources = [s for s in [data.get("fuente", "")] if s]

        if not data.get("convenio_encontrado") or confianza == "baja":
            return CheckResult(
                check_id,
                label,
                "uncertain",
                "❓ No se encontró información fiable sobre revisión salarial de este convenio para 2026. "
                "Verifica en el BOE o con el convenio en papel.",
                sources=sources,
                verified_at=today,
            )

        discs = []
        incremento = data.get("incremento_pactado_pct")
        salario_actualizado = data.get("salario_base_minimo_actualizado")
        tabla_boe = data.get("tabla_publicada_boe")
        clausula = data.get("clausula_revision_ipc", "")
        notas = data.get("notas", "")

        if salario_actualizado:
            discs.append(
                {
                    "label": "Salario base mínimo actualizado",
                    "perplexity": f"{salario_actualizado}€/mes",
                    "notas": f"Incremento pactado: {incremento}%" if incremento else "",
                }
            )

        if not tabla_boe:
            status = "warning" if incremento else "uncertain"
            msg = (
                f"⚠️ Convenio con posible revisión salarial {date.today().year}: "
                f"+{incremento}% pactado"
                if incremento
                else "❓ No se confirmó publicación de tablas salariales actualizadas en BOE"
            )
            if clausula:
                msg += f". Cláusula IPC: {clausula}"
            if notas:
                msg += f". Nota: {notas}"
            return CheckResult(
                check_id,
                label,
                status,
                msg,
                discrepancies=discs,
                sources=sources,
                verified_at=today,
            )

        msg = f"✅ Tablas salariales {date.today().year} publicadas en BOE."
        if incremento:
            msg += f" Incremento pactado: +{incremento}%."
        if clausula:
            msg += f" Cláusula revisión: {clausula}."
        return CheckResult(
            check_id, label, "ok", msg, discrepancies=discs, sources=sources, verified_at=today
        )

    # ------------------------------------------------------------------
    # Motor de llamada genérico
    # ------------------------------------------------------------------

    def _run_check(
        self,
        check_id: str,
        label: str,
        prompt: str,
        parser,
    ) -> CheckResult:
        today = date.today().isoformat()
        try:
            raw = self._call_perplexity(prompt)
            data = self._parse_json(raw)
            if data is None:
                return CheckResult(
                    check_id,
                    label,
                    "uncertain",
                    "❓ Respuesta de Perplexity no interpretable. Verifica manualmente.",
                    verified_at=today,
                )
            result = parser(data, label)
            result.check = check_id  # asegurar id correcto
            return result
        except ConnectionError as exc:
            return CheckResult(
                check_id,
                label,
                "unavailable",
                f"Sin conexión con Perplexity: {exc}",
                verified_at=today,
            )
        except Exception as exc:
            return CheckResult(
                check_id, label, "error", f"Error inesperado: {exc}", verified_at=today
            )

    def _call_perplexity(self, prompt: str) -> str:
        payload = json.dumps(
            {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres un experto en derecho laboral y fiscal español con acceso a internet. "
                            "Tu función es verificar datos normativos oficiales buscando en BOE, AEAT, "
                            "Ministerio de Inclusión y Seguridad Social. "
                            "Responde SIEMPRE con JSON válido sin texto adicional ni markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1000,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            _PERPLEXITY_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            raise ConnectionError(f"Perplexity HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(f"Perplexity connection: {exc.reason}") from exc

    @staticmethod
    def _parse_json(raw: str) -> dict | None:
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
        except (json.JSONDecodeError, IndexError):
            # Intentar extraer JSON si hay texto adicional
            import re

            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return None


def _unavailable_compat():
    class _U:
        status = "unavailable"
        message = "PERPLEXITY_API_KEY no configurada."
        discrepancies = []
        sources = []
        verified_at = ""
        is_advisory = True

        def to_dict(self):
            return {
                "status": self.status,
                "message": self.message,
                "discrepancies": [],
                "sources": [],
                "is_advisory": True,
                "our_rates": _OUR_SS_2026,
            }

    return _U()
