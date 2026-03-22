"""Verificador de tasas SS e IRPF vía Perplexity API.

IMPORTANTE: Esta verificación es ORIENTATIVA. Nunca bloquea operaciones ni
sustituye la revisión manual de la Orden de Cotización y el BOE/AEAT.

Si la API falla o no hay key, el sistema sigue funcionando (graceful degradation).

Uso:
    from rates_verifier import RatesVerifier
    v = RatesVerifier()
    result = v.verify_ss_rates()
    print(result["status"])  # "ok" | "warning" | "uncertain" | "unavailable"
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any


_PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
_TIMEOUT = 30

# Tasas que tenemos hardcoded — se comparan con lo que dice Perplexity
_OUR_RATES_2026 = {
    "anio": 2026,
    "empresa_cc": 23.60,
    "empresa_desempleo_indefinido": 5.50,
    "empresa_desempleo_temporal": 6.70,
    "empresa_fogasa": 0.20,
    "empresa_fp": 0.60,
    "empresa_mei": 0.58,
    "trab_cc": 4.70,
    "trab_desempleo_indefinido": 1.55,
    "trab_desempleo_temporal": 1.60,
    "trab_fp": 0.10,
    "trab_mei": 0.17,
    "base_min_mensual": 1323.00,
    "base_max_mensual": 4720.50,
}

# Tolerancia para comparar flotantes (diferencia ≤ 0.05 pp → ok)
_TOLERANCE = 0.05

# TTL de caché en segundos (24h — evita llamadas repetidas a Perplexity)
_CACHE_TTL = 86400


@dataclass
class RatesCheckResult:
    """Resultado de la verificación de tasas."""
    status: str          # "ok" | "warning" | "uncertain" | "unavailable"
    message: str
    discrepancies: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    verified_at: str = ""
    is_advisory: bool = True  # siempre True — nunca decisorio

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "discrepancies": self.discrepancies,
            "sources": self.sources,
            "verified_at": self.verified_at,
            "is_advisory": self.is_advisory,
            "our_rates": _OUR_RATES_2026,
        }


class RatesVerifier:
    """Verifica si las tasas SS/IRPF del sistema están actualizadas."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("PERPLEXITY_API_KEY", "")
        # Caché en memoria: evita llamar a Perplexity más de una vez al día
        self._cache: dict[str, Any] = {}
        self._cache_ts: float = 0.0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def verify_ss_rates(self, force: bool = False) -> RatesCheckResult:
        """Verifica las tasas de cotización SS para el año en curso.

        Args:
            force: Si True, ignora la caché y llama a Perplexity de nuevo.

        Returns:
            RatesCheckResult con status y discrepancias encontradas.
        """
        if not self.available:
            return RatesCheckResult(
                status="unavailable",
                message="Verificación no disponible: PERPLEXITY_API_KEY no configurada.",
            )

        # Servir desde caché si está fresco
        if not force and self._cache and (time.time() - self._cache_ts) < _CACHE_TTL:
            return RatesCheckResult(**self._cache)

        prompt = self._build_ss_prompt()

        try:
            raw = self._call_perplexity(prompt)
            result = self._parse_ss_response(raw)
            # Guardar en caché
            self._cache = {
                "status": result.status,
                "message": result.message,
                "discrepancies": result.discrepancies,
                "sources": result.sources,
                "verified_at": result.verified_at,
                "is_advisory": True,
            }
            self._cache_ts = time.time()
            return result
        except (ConnectionError, TimeoutError, json.JSONDecodeError) as exc:
            return RatesCheckResult(
                status="unavailable",
                message=f"Error al consultar Perplexity: {exc}",
            )

    # ------------------------------------------------------------------
    # Prompt SS
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ss_prompt() -> str:
        return """Necesito verificar las tasas de cotización a la Seguridad Social española para el año 2026 (Régimen General).

Responde SOLO con este JSON exacto (sin texto adicional):
{
  "anio": 2026,
  "empresa_cc": <porcentaje contingencias comunes empresa>,
  "empresa_desempleo_indefinido": <porcentaje desempleo indefinido empresa>,
  "empresa_desempleo_temporal": <porcentaje desempleo temporal empresa>,
  "empresa_fogasa": <porcentaje FOGASA empresa>,
  "empresa_fp": <porcentaje Formación Profesional empresa>,
  "empresa_mei": <porcentaje MEI empresa>,
  "trab_cc": <porcentaje contingencias comunes trabajador>,
  "trab_desempleo_indefinido": <porcentaje desempleo indefinido trabajador>,
  "trab_desempleo_temporal": <porcentaje desempleo temporal trabajador>,
  "trab_fp": <porcentaje Formación Profesional trabajador>,
  "trab_mei": <porcentaje MEI trabajador>,
  "base_min_mensual": <base mínima mensual en euros>,
  "base_max_mensual": <base máxima mensual en euros>,
  "fuente": "<referencia normativa o URL>",
  "confianza": "alta" | "media" | "baja"
}

Nuestros valores actuales para verificar:
- Empresa: CC=23.60%, desempleo indef=5.50%, desempleo temporal=6.70%, FOGASA=0.20%, FP=0.60%, MEI=0.58%
- Trabajador: CC=4.70%, desempleo indef=1.55%, desempleo temporal=1.60%, FP=0.10%, MEI=0.17%
- Base min=1.323€, Base max=4.720,50€

Si no encuentras datos fiables de 2026, usa el valor null para ese campo y pon "confianza": "baja"."""

    # ------------------------------------------------------------------
    # Llamada API (idéntica a ConvenioVerifier)
    # ------------------------------------------------------------------

    def _call_perplexity(self, prompt: str) -> str:
        payload = json.dumps({
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres un experto en derecho laboral y seguridad social español. "
                        "Tu misión es verificar datos normativos. "
                        "Responde SOLO con JSON válido, sin texto adicional, sin markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 800,
        }).encode("utf-8")

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

    # ------------------------------------------------------------------
    # Parse respuesta SS
    # ------------------------------------------------------------------

    def _parse_ss_response(self, raw: str) -> RatesCheckResult:
        from datetime import date

        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(clean)
        except (json.JSONDecodeError, IndexError):
            return RatesCheckResult(
                status="uncertain",
                message="No se pudo interpretar la respuesta de Perplexity. Verifica las tasas manualmente.",
            )

        confianza = data.get("confianza", "baja")
        if confianza == "baja":
            return RatesCheckResult(
                status="uncertain",
                message="Perplexity no encontró datos fiables de 2026. Verifica en BOE/AEAT.",
                sources=[data.get("fuente", "")] if data.get("fuente") else [],
                verified_at=date.today().isoformat(),
            )

        # Comparar campo a campo
        discrepancies: list[dict[str, Any]] = []
        fields_to_check = [
            ("empresa_cc", "Empresa — Contingencias Comunes"),
            ("empresa_desempleo_indefinido", "Empresa — Desempleo indefinido"),
            ("empresa_desempleo_temporal", "Empresa — Desempleo temporal"),
            ("empresa_fogasa", "Empresa — FOGASA"),
            ("empresa_fp", "Empresa — Formación Profesional"),
            ("empresa_mei", "Empresa — MEI"),
            ("trab_cc", "Trabajador — Contingencias Comunes"),
            ("trab_desempleo_indefinido", "Trabajador — Desempleo indefinido"),
            ("trab_desempleo_temporal", "Trabajador — Desempleo temporal"),
            ("trab_fp", "Trabajador — Formación Profesional"),
            ("trab_mei", "Trabajador — MEI"),
            ("base_min_mensual", "Base mínima mensual (€)"),
            ("base_max_mensual", "Base máxima mensual (€)"),
        ]

        for key, label in fields_to_check:
            their_val = data.get(key)
            our_val = _OUR_RATES_2026.get(key)
            if their_val is None or our_val is None:
                continue
            try:
                diff = abs(float(their_val) - float(our_val))
                # Para bases (€) usamos tolerancia relativa del 0.5%
                threshold = our_val * 0.005 if "base_" in key else _TOLERANCE
                if diff > threshold:
                    discrepancies.append({
                        "campo": key,
                        "label": label,
                        "nuestro": our_val,
                        "perplexity": float(their_val),
                        "diferencia": round(diff, 4),
                    })
            except (TypeError, ValueError):
                continue

        sources = [s for s in [data.get("fuente", "")] if s]
        verified_at = date.today().isoformat()

        if not discrepancies:
            return RatesCheckResult(
                status="ok",
                message=(
                    f"✅ Tasas SS 2026 verificadas — coinciden con "
                    f"{'fuente externa' if sources else 'Perplexity'}. "
                    f"Verificado el {verified_at}."
                ),
                sources=sources,
                verified_at=verified_at,
            )

        return RatesCheckResult(
            status="warning",
            message=(
                f"⚠️ Se detectaron {len(discrepancies)} posibles diferencias en las tasas SS 2026. "
                "Verifica manualmente con la Orden de Cotización oficial."
            ),
            discrepancies=discrepancies,
            sources=sources,
            verified_at=verified_at,
        )
