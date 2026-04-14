from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DespidoRequest(BaseModel):
    tipo_despido: str = Field(
        min_length=1,
        description="Tipo de despido: improcedente, objetivo, disciplinario, etc.",
    )
    fecha_inicio: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    salario_bruto_mensual: float = Field(gt=0, le=100000)
    employee_id: Optional[int] = None


class DespidoResponse(BaseModel):
    tipo: str
    indemnizacion_eur: float
    dias_indemnizacion: float
    salario_diario: float
    detalle: dict[str, Any]
    consejo: Optional[str] = None
