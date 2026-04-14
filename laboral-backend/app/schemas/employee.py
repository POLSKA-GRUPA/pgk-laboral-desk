from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    nif: str = Field(default="", max_length=20)
    naf: str = Field(default="", max_length=20)
    categoria: str = Field(min_length=1, max_length=100)
    contrato_tipo: str = Field(default="indefinido")
    jornada_horas: float = Field(default=40.0, ge=1.0, le=40.0)
    fecha_inicio: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    fecha_fin: Optional[str] = None
    salario_bruto_mensual: Optional[float] = Field(default=None, gt=0, le=100000)
    num_hijos: int = Field(default=0, ge=0, le=20)
    region: str = Field(default="generica", max_length=50)
    domicilio: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=200)
    telefono: str = Field(default="", max_length=30)
    notas: str = Field(default="", max_length=500)


class EmployeeUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=200)
    nif: Optional[str] = None
    naf: Optional[str] = None
    categoria: Optional[str] = Field(default=None, min_length=1, max_length=100)
    contrato_tipo: Optional[str] = None
    jornada_horas: Optional[float] = Field(default=None, ge=1.0, le=40.0)
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    salario_bruto_mensual: Optional[float] = Field(default=None, gt=0, le=100000)
    num_hijos: Optional[int] = Field(default=None, ge=0, le=20)
    region: Optional[str] = None
    domicilio: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    notas: Optional[str] = None


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company_id: Optional[int] = None
    nombre: str
    nif: str
    naf: str
    categoria: str
    contrato_tipo: str
    jornada_horas: float
    fecha_inicio: str
    fecha_fin: Optional[str] = None
    salario_bruto_mensual: Optional[float] = None
    num_hijos: int
    region: str
    domicilio: str
    email: str
    telefono: str
    notas: str
    status: str
    created_at: Optional[datetime] = None
