from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConvenioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    codigo_convenio: str
    ambito_geografico: str
    vigencia_inicio: Optional[str] = None
    vigencia_fin: Optional[str] = None
    sector: str
    activo: bool


class ConvenioDetail(ConvenioResponse):
    data_json: Optional[str] = None
