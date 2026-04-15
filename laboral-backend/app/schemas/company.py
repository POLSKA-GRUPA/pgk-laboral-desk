from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    cif: str = Field(default="", max_length=50)
    domicilio: str = Field(default="", max_length=300)
    ccc: str = Field(default="", max_length=50)
    convenio_id: str = Field(default="", max_length=100)
    sector: str = Field(default="", max_length=100)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    cif: str
    domicilio: str
    ccc: str
    convenio_id: str
    sector: str
    created_at: datetime | None = None
