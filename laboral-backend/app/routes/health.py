from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    checks = {"database": {"ok": False}}
    try:
        db.execute(text("SELECT 1"))
        checks["database"]["ok"] = True
    except Exception:
        pass

    return {
        "ok": all(c["ok"] for c in checks.values()),
        "version": settings.APP_VERSION,
        "checks": checks,
    }
