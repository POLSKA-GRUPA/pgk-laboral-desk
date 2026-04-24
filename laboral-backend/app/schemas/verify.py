from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VerifyConvenioRequest(BaseModel):
    sector: str = Field(min_length=1, max_length=200)
    provincia: str = "Estatal"
    codigo_convenio: str = ""
    vigencia_hasta: int | None = None


class VerifyResponse(BaseModel):
    """Respuesta de verify-rates / verify-convenio.

    `to_dict()` de los verificadores tiene shape variable segun resultado
    (ok, warnings, needs_review, error). Exponemos la estructura completa
    como dict libre para no acoplar el schema a los internals de Perplexity.
    """

    ok: bool = True
    details: dict[str, Any] = {}
