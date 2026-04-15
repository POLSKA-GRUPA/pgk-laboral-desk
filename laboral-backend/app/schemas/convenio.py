from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ConvenioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    codigo_convenio: str
    ambito_geografico: str
    vigencia_inicio: str | None = None
    vigencia_fin: str | None = None
    sector: str
    activo: bool


class ConvenioDetail(ConvenioResponse):
    data_json: str | None = None
