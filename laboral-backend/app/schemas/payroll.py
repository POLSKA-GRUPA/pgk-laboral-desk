from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NominaRequest(BaseModel):
    employee_id: int
    periodo: str = Field(pattern=r"^\d{4}-\d{2}$")
    convenio_id: str | None = None


class NominaResponse(BaseModel):
    employee_id: int
    periodo: str
    devengos: dict[str, Any]
    deducciones: dict[str, Any]
    neto: float
    coste_empresa: float
    pdf_url: str | None = None


class BulkPayrollRequest(BaseModel):
    company_id: int | None = None
    periodo: str = Field(pattern=r"^\d{4}-\d{2}$")
