from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClientRegisterRequest(BaseModel):
    empresa: str = Field(min_length=1, max_length=200)
    cif: str = Field(min_length=1, max_length=50)
    convenio_id: str = Field(min_length=1, max_length=200)
    provincia: str = ""
    comunidad_autonoma: str = ""
    cnae: str = ""


class ClientResponse(BaseModel):
    id: int
    empresa: str
    cif: str
    convenio_id: str
    provincia: str = ""
    comunidad_autonoma: str = ""
    cnae: str = ""


class ClientSimulateRequest(BaseModel):
    category: str = Field(min_length=1, max_length=200)
    contract_type: str = "indefinido"
    weekly_hours: float = 40.0
    seniority_years: int = 0
    extras_prorated: bool = False
    num_children: int = 0
    children_under_3: int = 0
    region: str = "generica"
    contract_days: int | None = None


class ClientSimulateResponse(BaseModel):
    """Resultado de simulacion asociada a un cliente concreto."""

    # La estructura del resultado la impone `LaboralEngine.simulate`; aqui sólo
    # anadimos el bloque `cliente` y dejamos el resto como dict libre para no
    # duplicar tipado ya cubierto en simulation.py.
    cliente: dict[str, Any]
    resultado: dict[str, Any]
