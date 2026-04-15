import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.payroll import BulkPayrollRequest, NominaRequest, NominaResponse
from app.services.payroll_service import PayrollService

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"

router = APIRouter(prefix="/nomina", tags=["payroll"])
_payroll_svc = PayrollService()


@router.post("", response_model=NominaResponse)
def generate_nomina(
    data: NominaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.employee import Employee

    emp = (
        db.query(Employee)
        .filter(
            Employee.id == data.employee_id,
            Employee.user_id == current_user.id,
        )
        .first()
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    convenio_id = data.convenio_id or current_user.convenio_id or "convenio_acuaticas_2025_2027"

    result = _payroll_svc.generate_nomina(
        category=emp.categoria,
        contract_type=emp.contrato_tipo,
        weekly_hours=emp.jornada_horas,
        region=emp.region,
        num_children=emp.num_hijos,
        convenio_id=convenio_id,
    )

    return NominaResponse(
        employee_id=emp.id,
        periodo=data.periodo,
        devengos=result.get("devengos", {}),
        deducciones=result.get("deducciones", {}),
        neto=result.get("neto_trabajador_mes_eur", 0),
        coste_empresa=result.get("coste_total_empresa_mes_eur", 0),
    )


@router.post("/bulk", response_model=list[NominaResponse])
def bulk_payroll(
    data: BulkPayrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.employee import Employee

    query = db.query(Employee).filter(
        Employee.user_id == current_user.id,
        Employee.status == "activo",
    )
    employees = query.all()
    if not employees:
        return []

    convenio_id = current_user.convenio_id or "convenio_acuaticas_2025_2027"
    emp_dicts = [
        {
            "id": e.id,
            "nombre": e.nombre,
            "categoria": e.categoria,
            "contrato_tipo": e.contrato_tipo,
            "jornada_horas": e.jornada_horas,
            "num_hijos": e.num_hijos,
            "region": e.region,
        }
        for e in employees
    ]

    results = _payroll_svc.bulk_payroll(emp_dicts, convenio_id, data.periodo)
    return [
        NominaResponse(
            employee_id=r.get("employee_id", 0),
            periodo=data.periodo,
            devengos=r.get("devengos", {}),
            deducciones=r.get("deducciones", {}),
            neto=r.get("neto_trabajador_mes_eur", 0),
            coste_empresa=r.get("coste_total_empresa_mes_eur", 0),
        )
        for r in results
    ]


def _load_convenio_safe(convenio_id: str) -> dict:
    safe_name = Path(convenio_id).name
    path = _DATA_DIR / f"{safe_name}.json"
    if not path.resolve().is_relative_to(_DATA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Convenio ID invalido")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Convenio no encontrado")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/{employee_id}/{periodo}")
def get_employee_nomina(
    employee_id: int,
    periodo: str,
    fmt: str = "pdf",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.employee import Employee
    from app.services.engine import LaboralEngine

    emp = (
        db.query(Employee)
        .filter(
            Employee.id == employee_id,
            Employee.user_id == current_user.id,
        )
        .first()
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    convenio_id = current_user.convenio_id or "convenio_acuaticas_2025_2027"
    convenio_data = _load_convenio_safe(convenio_id)
    engine = LaboralEngine(convenio_data)
    sim = engine.simulate(
        category=emp.categoria,
        contract_type=emp.contrato_tipo,
        weekly_hours=emp.jornada_horas,
        seniority_years=0,
        num_children=emp.num_hijos,
        region=emp.region or "generica",
    )

    if "error" in sim:
        raise HTTPException(status_code=400, detail=sim["error"])

    try:
        from app.services.nomina_pdf import (
            DatosEmpresa,
            build_nomina_from_simulation,
            generate_nomina_html_string,
            generate_nomina_pdf,
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="Modulo de generacion PDF no disponible") from None

    nomina = build_nomina_from_simulation(
        sim,
        empresa=DatosEmpresa(nombre=current_user.empresa_nombre or ""),
        trabajador_extra={
            "nombre": emp.nombre,
            "nif": emp.nif,
            "naf": emp.naf,
            "puesto": emp.categoria,
        },
        periodo_str=periodo,
    )

    if fmt == "html":
        html = generate_nomina_html_string(nomina)
        return Response(content=html, media_type="text/html")

    try:
        pdf_bytes = generate_nomina_pdf(nomina)
    except RuntimeError:
        html = generate_nomina_html_string(nomina)
        return Response(content=html, media_type="text/html")

    nombre_safe = emp.nombre.replace(" ", "_")[:30]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pre_nomina_{nombre_safe}.pdf"'},
    )
