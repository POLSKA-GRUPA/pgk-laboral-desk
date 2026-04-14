"""SEPE Contrat@ request/response schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ContratoGeneracionRequest(BaseModel):
    employee_id: int = Field(gt=0)
    company_id: Optional[int] = Field(default=None, gt=0)
    contract_type_override: Optional[str] = Field(default=None, max_length=50)
    fecha_inicio: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    fecha_fin: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    nivel_formativo: str = Field(default="40", max_length=2)
    codigo_ocupacion: str = Field(default="0000", max_length=8)
    municipio_ct: str = Field(default="", max_length=5)
    ind_discapacidad: str = Field(default="", max_length=1)
    codigo_programa_empleo: str = Field(default="", max_length=2)
    causa_sustitucion: str = Field(default="", max_length=2)
    horas_jornada_parcial: float = Field(default=0.0, ge=0.0)
    horas_convenio: float = Field(default=0.0, ge=0.0)
    tipo_jornada: str = Field(default="A", max_length=1)
    actividad_sin_fecha_cierta: bool = Field(default=False)


class ContratoGeneracionResponse(BaseModel):
    success: bool
    sepe_code: str
    sepe_element: str
    contract_description: str
    xml_size_bytes: int
    validation: ValidationResultSchema
    warnings: list[str] = []


class ValidationResultSchema(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class CodeTableResponse(BaseModel):
    table_name: str
    description: str
    codes: dict[str, str]


class CodeTableListResponse(BaseModel):
    tables: dict[str, str]


class ContractTypeMappingResponse(BaseModel):
    mappings: list[dict]
