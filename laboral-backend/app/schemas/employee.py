from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    nif: str = Field(default="", max_length=20)
    naf: str = Field(default="", max_length=20)
    categoria: str = Field(min_length=1, max_length=100)
    contrato_tipo: str = Field(default="indefinido")
    jornada_horas: float = Field(default=40.0, ge=1.0, le=40.0)
    fecha_inicio: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    fecha_fin: str | None = None
    salario_bruto_mensual: float | None = Field(default=None, gt=0, le=100000)
    num_hijos: int = Field(default=0, ge=0, le=20)
    region: str = Field(default="generica", max_length=50)
    domicilio: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=200)
    telefono: str = Field(default="", max_length=30)
    notas: str = Field(default="", max_length=500)


class EmployeeUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    nif: str | None = None
    naf: str | None = None
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    contrato_tipo: str | None = None
    jornada_horas: float | None = Field(default=None, ge=1.0, le=40.0)
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    salario_bruto_mensual: float | None = Field(default=None, gt=0, le=100000)
    num_hijos: int | None = Field(default=None, ge=0, le=20)
    region: str | None = None
    domicilio: str | None = None
    email: str | None = None
    telefono: str | None = None
    notas: str | None = None


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company_id: int | None = None
    nombre: str
    nif: str
    naf: str
    categoria: str
    contrato_tipo: str
    jornada_horas: float
    fecha_inicio: str
    fecha_fin: str | None = None
    salario_bruto_mensual: float | None = None
    num_hijos: int
    region: str
    domicilio: str
    email: str
    telefono: str
    notas: str
    status: str
    created_at: datetime | None = None
