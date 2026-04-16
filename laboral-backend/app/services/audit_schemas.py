"""Modelos Pydantic para el sistema de auditoría de nóminas — PGK Laboral Desk."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuditFinding(BaseModel):
    """Hallazgo individual de auditoría."""

    code: str
    dimension: str
    severity: str
    confidence: int = Field(ge=0, le=100)
    title: str
    description: str
    worker_name: str
    period: str
    expected_value: float | None = None
    actual_value: float | None = None
    deviation: float | None = None
    reference: str = ""
    fix_suggestion: str = ""


class WorkerAuditResult(BaseModel):
    """Resultado de auditoría por trabajador."""

    worker_name: str
    nif: str
    grupo_profesional: str
    grupo_cotizacion: str
    periodo: str
    findings: list[AuditFinding] = []
    total_devengado: float = 0.0
    liquido: float = 0.0
    coste_empresa: float = 0.0
    parse_errors: list[str] = []


class AuditReport(BaseModel):
    """Informe completo de auditoría de nóminas."""

    empresa: str
    cif: str
    ccc: str
    convenio: str
    periodo: str
    workers: list[WorkerAuditResult] = []
    findings: list[AuditFinding] = []
    summary: dict[str, int] = Field(
        default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0}
    )
    audit_timestamp: str = ""


class AuditRequest(BaseModel):
    """Petición de auditoría."""

    pdf_folder: str
    convenio_id: str = "convenio_acuaticas_2025_2027"
    empresa_nombre: str = ""
    empresa_cif: str = ""
    empresa_ccc: str = ""
