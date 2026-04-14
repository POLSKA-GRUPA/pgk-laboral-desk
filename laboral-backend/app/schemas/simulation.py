from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SimulateRequest(BaseModel):
    category: str = Field(min_length=1, max_length=200)
    contract_type: str = Field(default="indefinido")
    weekly_hours: float = Field(default=40.0, ge=1.0, le=40.0)
    seniority_years: int = Field(default=0, ge=0, le=60)
    num_children: int = Field(default=0, ge=0, le=20)
    children_under_3: int = Field(default=0, ge=0, le=20)
    region: str = Field(default="generica")
    contract_days: Optional[int] = Field(default=None, ge=1)
    convenio_id: Optional[str] = None


class SimulateResponse(BaseModel):
    categoria: str
    salario_bruto_mensual: float
    coste_total_empresa_mes_eur: float
    coste_total_empresa_anual_eur: float
    neto_trabajador_mes_eur: float
    desglose_ss: dict[str, Any]
    desglose_irpf: dict[str, Any]
    traces: list[str] = []
