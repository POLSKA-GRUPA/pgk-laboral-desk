import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.audit_schemas import AuditReport
from app.services.nomina_audit_engine import NominaAuditEngine
from app.services.nomina_audit_parser import parse_month_folder, parse_nomina

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"

router = APIRouter(prefix="/audit", tags=["audit"])


@router.post("/nomina")
async def audit_nomina_files(
    files: list[UploadFile],
    convenio_id: str = "convenio_acuaticas_2025_2027",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    nominas = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for f in files:
            if not f.filename or not f.filename.lower().endswith(".pdf"):
                continue
            dest = Path(tmpdir) / f.filename
            content = await f.read()
            dest.write_bytes(content)
            parsed = parse_nomina(dest)
            if parsed and parsed.total_devengado > 0:
                nominas.append(parsed)

    if not nominas:
        raise HTTPException(
            status_code=400, detail="No se pudieron parsear nóminas válidas de los archivos subidos"
        )

    convenio = _load_convenio(convenio_id)
    engine = NominaAuditEngine(convenio_data=convenio)
    report = engine.audit_month(nominas)
    return report.model_dump()


@router.post("/nomina-folder")
async def audit_nomina_folder(
    folder_path: str,
    convenio_id: str = "convenio_acuaticas_2025_2027",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    folder = Path(folder_path)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Carpeta no encontrada: {folder_path}")

    nominas = parse_month_folder(folder)
    if not nominas:
        raise HTTPException(
            status_code=400, detail="No se encontraron nóminas válidas en la carpeta"
        )

    convenio = _load_convenio(convenio_id)
    engine = NominaAuditEngine(convenio_data=convenio)
    report = engine.audit_month(nominas)
    return report.model_dump()


def _load_convenio(convenio_id: str) -> dict:
    path = _DATA_DIR / f"{convenio_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Convenio no encontrado: {convenio_id}")
    with open(path) as f:
        return json.load(f)
