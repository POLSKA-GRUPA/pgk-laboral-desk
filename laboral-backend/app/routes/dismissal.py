import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.dismissal import DespidoRequest, DespidoResponse
from app.services.engine import LaboralEngine
from app.services.validation import validate_despido_params

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"

router = APIRouter(prefix="/despido", tags=["dismissal"])


@router.post("", response_model=DespidoResponse)
def calculate_dismissal(
    data: DespidoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_despido_params(
        tipo_despido=data.tipo_despido,
        fecha_inicio=data.fecha_inicio,
        salario_bruto_mensual=data.salario_bruto_mensual,
    )

    convenio_id = current_user.convenio_id or "convenio_acuaticas_2025_2027"
    safe_name = Path(convenio_id).name
    convenio_path = _DATA_DIR / f"{safe_name}.json"
    if not convenio_path.resolve().is_relative_to(_DATA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Convenio ID invalido")
    if not convenio_path.exists():
        raise HTTPException(status_code=404, detail="Convenio no encontrado")

    convenio_data = json.loads(convenio_path.read_text(encoding="utf-8"))
    engine = LaboralEngine(convenio_data)

    result = engine.calcular_despido(
        tipo_despido=data.tipo_despido,
        fecha_inicio=data.fecha_inicio,
        salario_bruto_mensual=data.salario_bruto_mensual,
    )

    return DespidoResponse(
        tipo=data.tipo_despido,
        indemnizacion_eur=result.get("indemnizacion_eur", 0),
        dias_indemnizacion=result.get("dias_indemnizacion", 0),
        salario_diario=result.get("salario_diario", 0),
        detalle=result,
        consejo=result.get("consejo"),
    )
