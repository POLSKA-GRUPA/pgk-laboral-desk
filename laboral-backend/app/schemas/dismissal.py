from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DespidoRequest(BaseModel):
    tipo_despido: str = Field(
        min_length=1,
        description="Tipo de despido: improcedente, objetivo, disciplinario, etc.",
    )
    fecha_inicio: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    salario_bruto_mensual: float = Field(gt=0, le=100000)
    employee_id: int | None = None


class DespidoResponse(BaseModel):
    tipo: str
    tipo_despido_label: str = ""
    indemnizacion_eur: float
    antiguedad_anos: float = 0.0
    antiguedad_dias: int = 0
    salario_diario_eur: float = 0.0
    salario_bruto_mensual_eur: float = 0.0
    total_eur: float = 0.0
    finiquito: dict[str, Any] | None = None
    escenarios: dict[str, Any] | None = None
    detalle: dict[str, Any]
    consejo: list[str] | None = None
