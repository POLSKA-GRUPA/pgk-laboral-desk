import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.convenio import ConvenioDetail, ConvenioResponse

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"

router = APIRouter(prefix="/convenios", tags=["convenios"])


def _list_convenio_files() -> list[dict]:
    results = []
    for p in sorted(_DATA_DIR.glob("convenio_*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            resumen = data.get("resumen_operativo", {})
            results.append(
                {
                    "id": 0,
                    "nombre": data.get("titulo", p.stem),
                    "codigo_convenio": p.stem,
                    "ambito_geografico": resumen.get("ambito_geografico", ""),
                    "vigencia_inicio": resumen.get("vigencia_inicio", ""),
                    "vigencia_fin": resumen.get("vigencia_fin", ""),
                    "sector": resumen.get("sector", ""),
                    "activo": True,
                }
            )
        except Exception:
            continue
    for i, r in enumerate(results, 1):
        r["id"] = i
    return results


@router.get("", response_model=list[ConvenioResponse])
def list_convenios(current_user: User = Depends(get_current_user)):
    return _list_convenio_files()


@router.get("/{convenio_id}", response_model=ConvenioDetail)
def get_convenio(
    convenio_id: str,
    current_user: User = Depends(get_current_user),
):
    safe_name = Path(convenio_id).name
    path = _DATA_DIR / f"{safe_name}.json"
    if not path.resolve().is_relative_to(_DATA_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Convenio ID invalido")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Convenio no encontrado")
    data = json.loads(path.read_text(encoding="utf-8"))
    resumen = data.get("resumen_operativo", {})
    return ConvenioDetail(
        id=0,
        nombre=data.get("titulo", convenio_id),
        codigo_convenio=convenio_id,
        ambito_geografico=resumen.get("ambito_geografico", ""),
        vigencia_inicio=resumen.get("vigencia_inicio", ""),
        vigencia_fin=resumen.get("vigencia_fin", ""),
        sector=resumen.get("sector", ""),
        activo=True,
        data_json=json.dumps(data, ensure_ascii=False),
    )
