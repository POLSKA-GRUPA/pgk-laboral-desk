import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.employee import Employee
from app.models.user import User
from app.services.engine import LaboralEngine

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"

router = APIRouter(tags=["employees"])


class EmployeeDismissalRequest(BaseModel):
    tipo_despido: str = "improcedente"
    fecha_despido: str | None = None
    dias_vacaciones_pendientes: int = 0
    dias_preaviso_empresa: int = 0


@router.post("/api/employees/{employee_id}/despido")
def calculate_employee_dismissal(
    employee_id: int,
    data: EmployeeDismissalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    emp = (
        db.query(Employee)
        .filter(
            Employee.id == employee_id,
            Employee.user_id == current_user.id,
        )
        .first()
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    convenio_id = current_user.convenio_id or "convenio_acuaticas_2025_2027"
    safe_name = Path(convenio_id).name
    path = _DATA_DIR / f"{safe_name}.json"
    if not path.resolve().is_relative_to(_DATA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Convenio ID invalido")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Convenio no encontrado")
    convenio_data = json.loads(path.read_text(encoding="utf-8"))

    engine = LaboralEngine(convenio_data)

    salario = emp.salario_bruto_mensual
    if not salario:
        sim = engine.simulate(
            category=emp.categoria,
            contract_type=emp.contrato_tipo,
            weekly_hours=emp.jornada_horas,
        )
        salario = sim.get("bruto_mensual_eur", 1000.0) if "error" not in sim else 1000.0

    result = engine.calcular_despido(
        tipo_despido=data.tipo_despido,
        fecha_inicio=emp.fecha_inicio,
        salario_bruto_mensual=float(salario),
        fecha_despido=data.fecha_despido,
        dias_vacaciones_pendientes=data.dias_vacaciones_pendientes,
        dias_preaviso_empresa=data.dias_preaviso_empresa,
        weekly_hours=emp.jornada_horas,
        nombre_trabajador=emp.nombre,
        categoria=emp.categoria,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
