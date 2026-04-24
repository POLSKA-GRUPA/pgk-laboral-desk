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
    codigo_contrato_sepe: str = ""
    fecha_llamamiento: str | None = None
    fecha_cese_temporada: str | None = None
    temporada: str = ""
    estado_llamamiento: str = ""
    dias_trabajados_temporada: int = 0
    created_at: datetime | None = None


class BulkImportRow(BaseModel):
    """Una fila de la plantilla CSV de alta masiva.

    Campos mínimos obligatorios: nombre, categoría, fecha_inicio. NIF y NAF
    opcionales pero si vienen se validan con dígito de control.
    """

    nombre: str
    nif: str = ""
    naf: str = ""
    categoria: str
    contrato_tipo: str = "indefinido"
    codigo_contrato_sepe: str = ""
    jornada_horas: float = 40.0
    fecha_inicio: str
    fecha_fin: str | None = None
    salario_bruto_mensual: float | None = None
    num_hijos: int = 0
    region: str = "generica"
    domicilio: str = ""
    email: str = ""
    telefono: str = ""
    sexo: str = "1"
    fecha_nacimiento: str = ""
    nacionalidad: str = "724"
    municipio_residencia: str = ""
    pais_residencia: str = "724"
    temporada: str = ""
    notas: str = ""


class BulkImportError(BaseModel):
    row: int
    field: str
    value: str
    message: str


class BulkImportResult(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    dry_run: bool
    created: int
    errors: list[BulkImportError]
    created_ids: list[int] = Field(default_factory=list)
