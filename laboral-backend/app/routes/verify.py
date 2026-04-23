"""Verificacion externa (SS/IRPF/SMI y convenios) via Perplexity.

Porta `/api/verify-rates` y `/api/verify-convenio` desde Flask v2. Los dos
servicios (`RatesVerifier`, `ConvenioVerifier`) ya existian en
`app.services.*`; este modulo solo cablea los endpoints HTTP.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.verify import VerifyConvenioRequest, VerifyResponse
from app.services.convenio_verifier import ConvenioVerifier
from app.services.rates_verifier import RatesVerifier

router = APIRouter(tags=["verify"])

_rates_verifier = RatesVerifier()
_convenio_verifier = ConvenioVerifier()


@router.get("/verify-rates", response_model=VerifyResponse)
def verify_rates(
    force: bool = False,
    current_user: User = Depends(get_current_user),
):
    """Verifica topes SS, tramos IRPF, SMI y vigencia de convenios cargados.

    `?force=true` salta la cache de 24h.
    """
    del current_user
    if not _rates_verifier.available:
        raise HTTPException(
            status_code=503,
            detail="Verificacion no disponible. Configura PERPLEXITY_API_KEY.",
        )
    result = _rates_verifier.verify_all(force=force)
    payload = result.to_dict()
    return VerifyResponse(ok=bool(payload.get("ok", True)), details=payload)


@router.post("/verify-convenio", response_model=VerifyResponse)
def verify_convenio(
    data: VerifyConvenioRequest,
    current_user: User = Depends(get_current_user),
):
    """Verifica vigencia + actualidad de un convenio concreto via Perplexity."""
    del current_user
    if not _convenio_verifier.available:
        raise HTTPException(
            status_code=503,
            detail="Verificacion no disponible. Configura PERPLEXITY_API_KEY.",
        )
    result = _convenio_verifier.verify(
        sector=data.sector,
        provincia=data.provincia,
        codigo_convenio=data.codigo_convenio,
        vigencia_hasta=data.vigencia_hasta,
    )
    payload = result.to_dict()
    return VerifyResponse(ok=bool(payload.get("ok", True)), details=payload)
