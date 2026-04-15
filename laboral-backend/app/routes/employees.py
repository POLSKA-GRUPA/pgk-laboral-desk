from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.employee import Employee
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeResponse])
def list_employees(
    status_filter: str = Query("activo", alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Employee).filter(
        Employee.user_id == current_user.id,
        Employee.status == status_filter,
    )
    return query.order_by(Employee.nombre).offset(offset).limit(limit).all()


@router.post("", response_model=EmployeeResponse, status_code=201)
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    emp = Employee(
        user_id=current_user.id,
        nombre=data.nombre,
        nif=data.nif,
        naf=data.naf,
        categoria=data.categoria,
        contrato_tipo=data.contrato_tipo,
        jornada_horas=data.jornada_horas,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        salario_bruto_mensual=data.salario_bruto_mensual,
        num_hijos=data.num_hijos,
        region=data.region,
        domicilio=data.domicilio,
        email=data.email,
        telefono=data.telefono,
        notas=data.notas,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
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
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return emp


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
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
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(emp, key, value)
    db.commit()
    db.refresh(emp)
    return emp


@router.delete("/{employee_id}", status_code=204)
def deactivate_employee(
    employee_id: int,
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
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    emp.status = "baja"
    db.commit()
