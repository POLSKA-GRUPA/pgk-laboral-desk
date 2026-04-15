"""SEPE Contrat@ API endpoints.

Generate and validate Contrat@ XML files for SEPE communication.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.employee import Employee
from app.models.user import User
from app.schemas.sepe import (
    CodeTableListResponse,
    CodeTableResponse,
    ContractTypeMappingResponse,
    ContratoGeneracionRequest,
    ContratoGeneracionResponse,
    ValidationResultSchema,
)
from app.services.sepe_code_tables import CONTRACT_TYPES, get_table, list_tables
from app.services.sepe_mapper import list_available_types
from app.services.sepe_validator import validate_xml
from app.services.sepe_xml_generator import contrato_xml_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sepe/contrata", tags=["SEPE Contrat@"])


@router.get("/code-tables", response_model=CodeTableListResponse)
def list_code_tables(
    current_user: User = Depends(get_current_user),
):
    return CodeTableListResponse(tables=list_tables())


@router.get("/code-tables/{table_name}", response_model=CodeTableResponse)
def get_code_table(
    table_name: str,
    current_user: User = Depends(get_current_user),
):
    try:
        codes = get_table(table_name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    all_tables = list_tables()
    return CodeTableResponse(
        table_name=table_name,
        description=all_tables.get(table_name, ""),
        codes=codes,
    )


@router.get("/contract-types", response_model=ContractTypeMappingResponse)
def get_contract_type_mappings(
    current_user: User = Depends(get_current_user),
):
    return ContractTypeMappingResponse(mappings=list_available_types())


def _resolve_employee_company(
    request: ContratoGeneracionRequest, db: Session
) -> tuple:
    """Validate and resolve employee + company from the request. Returns (employee, company, contrato_tipo, fecha_inicio, fecha_fin)."""
    employee = db.query(Employee).filter(Employee.id == request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {request.employee_id} not found")

    company = None
    if request.company_id:
        company = db.query(Company).filter(Company.id == request.company_id).first()
    elif employee.company_id:
        company = db.query(Company).filter(Company.id == employee.company_id).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found. Provide company_id or assign employee to a company.",
        )

    if not employee.nif:
        raise HTTPException(
            status_code=422, detail="Employee must have a NIF to generate Contrat@ XML"
        )
    if not company.cif:
        raise HTTPException(
            status_code=422, detail="Company must have a CIF to generate Contrat@ XML"
        )
    if not company.ccc:
        raise HTTPException(
            status_code=422, detail="Company must have a Codigo de Cuenta de Cotizacion (CCC)"
        )

    contrato_tipo = request.contract_type_override or employee.contrato_tipo
    fecha_inicio = request.fecha_inicio or employee.fecha_inicio
    fecha_fin = request.fecha_fin or employee.fecha_fin

    if not fecha_inicio:
        raise HTTPException(status_code=422, detail="Contract fecha_inicio is required")

    return employee, company, contrato_tipo, fecha_inicio, fecha_fin


def _generate_xml(
    request: ContratoGeneracionRequest,
    employee: Employee,
    company: Company,
    contrato_tipo: str,
    fecha_inicio: str,
    fecha_fin: str | None,
) -> tuple:
    """Generate Contrat@ XML. Returns (xml_bytes, mapping, warnings)."""
    try:
        return contrato_xml_generator.generate(
            empresa_cif=company.cif,
            empresa_ccc=company.ccc,
            trabajador_nif=employee.nif,
            trabajador_nombre=employee.nombre,
            trabajador_sexo=employee.sexo,
            trabajador_fecha_nacimiento=employee.fecha_nacimiento,
            trabajador_nacionalidad=employee.nacionalidad,
            trabajador_municipio=employee.municipio_residencia,
            trabajador_pais_residencia=employee.pais_residencia,
            trabajador_naf=employee.naf,
            trabajador_domicilio=employee.domicilio,
            contrato_tipo_pgk=contrato_tipo,
            contrato_jornada=employee.jornada_horas,
            contrato_fecha_inicio=fecha_inicio,
            contrato_fecha_fin=fecha_fin,
            contrato_nivel_formativo=request.nivel_formativo,
            contrato_ocupacion=request.codigo_ocupacion,
            contrato_nacionalidad_ct="724",
            contrato_municipio_ct=company.municipio_ct or request.municipio_ct,
            contrato_ind_discapacidad=request.ind_discapacidad,
            contrato_codigo_programa_empleo=request.codigo_programa_empleo,
            contrato_ind_ere_vigente="N",
            contrato_causa_sustitucion=request.causa_sustitucion,
            contrato_horas_jornada_parcial=request.horas_jornada_parcial,
            contrato_horas_convenio=request.horas_convenio,
            contrato_tipo_jornada=request.tipo_jornada,
            contrato_actividad_sin_fecha_cierta=request.actividad_sin_fecha_cierta,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/generate-xml", response_model=ContratoGeneracionResponse)
def generate_contrato_xml(
    request: ContratoGeneracionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee, company, contrato_tipo, fecha_inicio, fecha_fin = _resolve_employee_company(
        request, db
    )
    xml_bytes, mapping, gen_warnings = _generate_xml(
        request, employee, company, contrato_tipo, fecha_inicio, fecha_fin
    )

    validation = validate_xml(xml_bytes)
    contract_desc = CONTRACT_TYPES.get(mapping.sepe_code, mapping.pgk_type)

    return ContratoGeneracionResponse(
        success=validation.valid,
        sepe_code=mapping.sepe_code,
        sepe_element=mapping.sepe_element,
        contract_description=contract_desc,
        xml_size_bytes=len(xml_bytes),
        validation=ValidationResultSchema(
            valid=validation.valid,
            errors=validation.errors,
            warnings=validation.warnings,
        ),
        warnings=gen_warnings,
    )


@router.post("/generate-xml/download")
def download_contrato_xml(
    request: ContratoGeneracionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee, company, contrato_tipo, fecha_inicio, fecha_fin = _resolve_employee_company(
        request, db
    )
    xml_bytes, mapping, _ = _generate_xml(
        request, employee, company, contrato_tipo, fecha_inicio, fecha_fin
    )

    filename = f"contrata_{mapping.sepe_code}_{employee.nif}_{fecha_inicio.replace('-', '')}.xml"

    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
