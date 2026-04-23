"""Gestion multi-cliente (empresas asesoradas por PGK).

Porta `/api/clients` y `/api/clients/<id>/simulate` desde Flask v2 a FastAPI.
Sigue usando `ClientManager` (sqlite propio en `db/pgk_laboral.db`) para
evitar una migracion de datos en este PR; la migracion a SQLAlchemy puede
hacerse despues sin romper API.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas.client import (
    ClientRegisterRequest,
    ClientResponse,
    ClientSimulateRequest,
    ClientSimulateResponse,
)
from app.services.client_manager import ClientManager
from app.services.engine import LaboralEngine

router = APIRouter(prefix="/clients", tags=["clients"])


@lru_cache(maxsize=1)
def _get_client_mgr() -> ClientManager:
    """ClientManager singleton con init-on-first-use.

    Importar este modulo NO debe tener efectos colaterales en disco
    (el constructor crea `db/pgk_laboral.db` al llamar `init_tables`).
    Esto evita que tests, CI runners o herramientas de introspeccion
    instancien sqlite en ubicaciones arbitrarias al leer rutas.
    """
    mgr = ClientManager()
    mgr.init_tables()
    return mgr


def _client_to_schema(client) -> ClientResponse:
    d = client.to_dict()
    return ClientResponse(
        id=int(d["id"]),
        empresa=d["empresa"],
        cif=d["cif"],
        convenio_id=d["convenio_id"],
        provincia=d.get("provincia", ""),
        comunidad_autonoma=d.get("comunidad_autonoma", ""),
        cnae=d.get("cnae", ""),
    )


@router.get("", response_model=list[ClientResponse])
def list_clients(_admin: User = Depends(require_admin)):
    return [ClientResponse(**c) for c in _get_client_mgr().list_clients()]


@router.post("", response_model=ClientResponse, status_code=201)
def register_client(
    data: ClientRegisterRequest,
    _admin: User = Depends(require_admin),
):
    mgr = _get_client_mgr()
    try:
        client_id = mgr.register_client(
            empresa=data.empresa,
            cif=data.cif,
            convenio_id=data.convenio_id,
            provincia=data.provincia,
            comunidad_autonoma=data.comunidad_autonoma,
            cnae=data.cnae,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    client = mgr.get_client(client_id)
    if client is None:  # pragma: no cover — defensivo, register_client acaba de crearlo
        raise HTTPException(status_code=500, detail="Cliente no encontrado tras registro")
    return _client_to_schema(client)


@router.post("/{client_id}/simulate", response_model=ClientSimulateResponse)
def simulate_for_client(
    client_id: int,
    data: ClientSimulateRequest,
    current_user: User = Depends(get_current_user),
):
    """Simula una nomina usando el convenio del cliente concreto."""
    del current_user  # sólo autentica, la politica de acceso por rol se hara en PR futuro
    client = _get_client_mgr().get_client(client_id)
    if not client:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )
    try:
        client_engine = LaboralEngine.from_convenio_id(client.convenio_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Convenio no encontrado: {client.convenio_id}",
        ) from exc

    result = client_engine.simulate(
        category=data.category,
        contract_type=data.contract_type,
        weekly_hours=data.weekly_hours,
        seniority_years=data.seniority_years,
        extras_prorated=data.extras_prorated,
        num_children=data.num_children,
        children_under_3=data.children_under_3,
        region=data.region,
        contract_days=data.contract_days,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return ClientSimulateResponse(
        cliente={"empresa": client.empresa, "cif": client.cif},
        resultado=result,
    )
