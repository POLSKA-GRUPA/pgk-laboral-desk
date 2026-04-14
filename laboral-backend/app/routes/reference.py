import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.user import User
from app.services.engine import LaboralEngine

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"

router = APIRouter(prefix="/reference", tags=["reference"])


def _get_engine_for_user(current_user: User) -> LaboralEngine:
    convenio_id = current_user.convenio_id or "convenio_acuaticas_2025_2027"
    safe_name = Path(convenio_id).name
    path = _DATA_DIR / f"{safe_name}.json"
    if not path.resolve().is_relative_to(_DATA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Convenio ID invalido")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Convenio no encontrado")
    data = json.loads(path.read_text(encoding="utf-8"))
    return LaboralEngine(data)


@router.get("/categories")
def get_categories(current_user: User = Depends(get_current_user)):
    return _get_engine_for_user(current_user).get_categories()


@router.get("/contract-types")
def get_contract_types(current_user: User = Depends(get_current_user)):
    return _get_engine_for_user(current_user).get_contract_types()


@router.get("/regions")
def get_regions(current_user: User = Depends(get_current_user)):
    return _get_engine_for_user(current_user).get_regions()


@router.get("/tipos-despido")
def get_tipos_despido(current_user: User = Depends(get_current_user)):
    engine = _get_engine_for_user(current_user)
    if hasattr(engine, "get_tipos_despido"):
        return engine.get_tipos_despido()
    return [
        {"value": t, "label": t.replace("_", " ").title()}
        for t in [
            "improcedente",
            "objetivo",
            "disciplinario",
            "disciplinario_procedente",
            "mutuo_acuerdo",
            "voluntario",
            "ere",
            "fin_contrato_temporal",
        ]
    ]
