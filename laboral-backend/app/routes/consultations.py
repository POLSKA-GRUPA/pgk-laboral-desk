from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.consultation import Consultation
from app.models.user import User

router = APIRouter(prefix="/consultations", tags=["consultations"])


@router.get("")
def list_consultations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Consultation)
        .filter(Consultation.user_id == current_user.id)
        .order_by(Consultation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "query_summary": r.query_summary,
            "result_data": r.result_data,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in rows
    ]
