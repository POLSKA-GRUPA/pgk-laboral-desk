import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.simulation import SimulateRequest, SimulateResponse
from app.services.engine import LaboralEngine
from app.services.validation import validate_simulation_params

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"

router = APIRouter(prefix="/simulate", tags=["simulation"])


def _load_convenio(convenio_id: str) -> dict:
    safe_name = Path(convenio_id).name
    path = _DATA_DIR / f"{safe_name}.json"
    if not path.resolve().is_relative_to(_DATA_DIR.resolve()):
        raise FileNotFoundError("Convenio ID invalido")
    if not path.exists():
        raise FileNotFoundError(f"Convenio no encontrado: {convenio_id}")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("", response_model=SimulateResponse)
def simulate(
    data: SimulateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_simulation_params(
        category=data.category,
        contract_type=data.contract_type,
        weekly_hours=data.weekly_hours,
        seniority_years=data.seniority_years,
        num_children=data.num_children,
        children_under_3=data.children_under_3,
        contract_days=data.contract_days,
    )

    convenio_id = data.convenio_id or current_user.convenio_id or "convenio_acuaticas_2025_2027"
    try:
        convenio_data = _load_convenio(convenio_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Convenio no encontrado: {convenio_id}") from None

    engine = LaboralEngine(convenio_data)
    result = engine.simulate(
        category=data.category,
        contract_type=data.contract_type,
        weekly_hours=data.weekly_hours,
        seniority_years=data.seniority_years,
        num_children=data.num_children,
        children_under_3=data.children_under_3,
        region=data.region,
        contract_days=data.contract_days,
    )

    from app.models.consultation import Consultation

    consultation = Consultation(
        user_id=current_user.id,
        query_summary=f"Simulacion: {data.category} {data.contract_type}",
        request_data=data.model_dump_json(),
        result_data=json.dumps(result, ensure_ascii=False),
    )
    db.add(consultation)
    db.commit()

    return SimulateResponse(
        categoria=result.get("categoria", data.category),
        salario_bruto_mensual=result.get("bruto_mensual_eur", 0),
        coste_total_empresa_mes_eur=result.get("coste_total_empresa_mes_eur", 0),
        coste_total_empresa_anual_eur=result.get("coste_total_empresa_anual_eur", 0),
        neto_trabajador_mes_eur=result.get("neto_mensual_eur", 0),
        desglose_ss=result.get("ss_detalle", {}),
        desglose_irpf=result.get("irpf_detalle", {}),
        traces=result.get("traces", []),
    )
