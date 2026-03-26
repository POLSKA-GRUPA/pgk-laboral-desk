"""Verificador de vigencia de convenios colectivos vía Perplexity API.

IMPORTANTE: Perplexity es SOLO orientativo. El resultado se presenta
al usuario como "verificación orientativa", NUNCA se usa para tomar
decisiones automáticas ni bloquear operaciones.

Si la API falla o no hay key, el sistema sigue funcionando (graceful degradation).

Uso:
    from convenio_verifier import ConvenioVerifier
    v = ConvenioVerifier()
    result = v.verify("Oficinas y Despachos", "Alicante", "03001005011983")
    print(result["status"])  # "verified" | "outdated" | "uncertain" | "unavailable"
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

_PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
_TIMEOUT = 30


@dataclass
class VerificationResult:
    """Resultado de la verificación de un convenio."""

    status: str  # "verified" | "outdated" | "uncertain" | "unavailable"
    message: str
    sources: list[str] = field(default_factory=list)
    perplexity_raw: str = ""
    is_advisory: bool = True  # siempre True — nunca decisorio

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "sources": self.sources,
            "is_advisory": self.is_advisory,
        }


class ConvenioVerifier:
    """Verifica si un convenio es el vigente usando Perplexity API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("PERPLEXITY_API_KEY", "")

    @property
    def available(self) -> bool:
        """True si hay API key configurada."""
        return bool(self.api_key)

    def verify(
        self,
        sector: str,
        provincia: str,
        codigo_convenio: str = "",
        vigencia_hasta: int | None = None,
    ) -> VerificationResult:
        """Verifica si el convenio indicado es el último vigente.

        Args:
            sector: Nombre del sector (ej. "Oficinas y Despachos").
            provincia: Provincia o "Estatal".
            codigo_convenio: Código REGCON del convenio.
            vigencia_hasta: Año fin de vigencia que tenemos registrado.

        Returns:
            VerificationResult con status y mensaje orientativo.
        """
        if not self.available:
            return VerificationResult(
                status="unavailable",
                message="Verificación no disponible: PERPLEXITY_API_KEY no configurada.",
            )

        prompt = self._build_prompt(sector, provincia, codigo_convenio, vigencia_hasta)

        try:
            raw = self._call_perplexity(prompt)
            return self._parse_response(raw, vigencia_hasta)
        except (ConnectionError, TimeoutError, json.JSONDecodeError) as exc:
            return VerificationResult(
                status="unavailable",
                message=f"Error al consultar Perplexity: {exc}",
            )

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(
        sector: str,
        provincia: str,
        codigo_convenio: str,
        vigencia_hasta: int | None,
    ) -> str:
        ambito = (
            f"de la provincia de {provincia}"
            if provincia.lower() != "estatal"
            else "de ámbito estatal"
        )
        parts = [
            f"¿Cuál es el último convenio colectivo vigente de {sector} {ambito} en España?",
            "Responde SOLO con estos datos en formato JSON:",
            '{"nombre": "...", "codigo_convenio": "...", "publicacion": "fecha o boletín", '
            '"vigencia_desde": año, "vigencia_hasta": año, "fuente": "URL o referencia"}',
        ]
        if codigo_convenio:
            parts.append(f"El código de convenio que tenemos registrado es: {codigo_convenio}.")
        if vigencia_hasta:
            parts.append(f"Nuestra vigencia registrada finaliza en {vigencia_hasta}.")
        parts.append(
            "Si no encuentras datos fiables, responde con un JSON con 'status': 'uncertain'."
        )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Llamada API
    # ------------------------------------------------------------------

    def _call_perplexity(self, prompt: str) -> str:
        payload = json.dumps(
            {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres un experto en derecho laboral español. "
                            "Responde SOLO con JSON válido, sin texto adicional."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 500,
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
                content = data["choices"][0]["message"]["content"]
                return content
        except urllib.error.HTTPError as exc:
            raise ConnectionError(f"Perplexity HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(f"Perplexity connection: {exc.reason}") from exc

    # ------------------------------------------------------------------
    # Parsing respuesta
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: str, our_vigencia: int | None) -> VerificationResult:
        """Parsea la respuesta de Perplexity y compara con nuestros datos."""
        # Intentar extraer JSON de la respuesta
        try:
            # Perplexity a veces envuelve en ```json ... ```
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(clean)
        except (json.JSONDecodeError, IndexError):
            return VerificationResult(
                status="uncertain",
                message="No se pudo interpretar la respuesta de Perplexity.",
                perplexity_raw=raw,
            )

        # Si Perplexity dice uncertain
        if data.get("status") == "uncertain":
            return VerificationResult(
                status="uncertain",
                message="Perplexity no encontró datos fiables sobre este convenio.",
                perplexity_raw=raw,
            )

        # Extraer datos
        their_vigencia = data.get("vigencia_hasta")
        nombre = data.get("nombre", "")
        fuente = data.get("fuente", "")
        publicacion = data.get("publicacion", "")
        sources = [s for s in [fuente, publicacion] if s]

        # Comparar
        if our_vigencia and their_vigencia:
            try:
                their_year = int(their_vigencia)
                if their_year <= our_vigencia:
                    return VerificationResult(
                        status="verified",
                        message=f"✅ Convenio vigente confirmado. {nombre} — vigencia hasta {their_year}.",
                        sources=sources,
                        perplexity_raw=raw,
                    )
                else:
                    return VerificationResult(
                        status="outdated",
                        message=(
                            f"⚠️ Posible convenio más reciente detectado: {nombre} "
                            f"— vigencia hasta {their_year} (nosotros: {our_vigencia}). "
                            "Verificar manualmente."
                        ),
                        sources=sources,
                        perplexity_raw=raw,
                    )
            except (ValueError, TypeError):
                pass

        return VerificationResult(
            status="uncertain",
            message=f"Datos encontrados pero no se pudo confirmar vigencia: {nombre}.",
            sources=sources,
            perplexity_raw=raw,
        )
