import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_parser import ChatParser

router = APIRouter(prefix="/chat", tags=["chat"])

_parser = ChatParser()
_chat_sessions: dict[str, dict] = {}

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"


def _load_convenio_safe(convenio_id: str) -> dict:
    safe_name = Path(convenio_id).name
    path = _DATA_DIR / f"{safe_name}.json"
    if not path.resolve().is_relative_to(_DATA_DIR.resolve()):
        raise FileNotFoundError("Convenio ID invalido")
    if not path.exists():
        raise FileNotFoundError(f"Convenio no encontrado: {convenio_id}")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_id = data.session_id or str(uuid.uuid4())
    ctx = _chat_sessions.get(session_id, {})

    convenio_id = data.convenio_id or current_user.convenio_id or "convenio_acuaticas_2025_2027"

    try:
        result = _parser.parse(data.message, context=ctx)
    except Exception as exc:
        return ChatResponse(
            response=f"Error al procesar la consulta: {exc}",
            traces=[],
            session_id=session_id,
        )

    action = result.get("action")
    new_ctx = result.get("context", {})

    if action in ("clarify_category", "need_params"):
        _chat_sessions[session_id] = new_ctx
        return ChatResponse(
            response=result.get("message", ""),
            session_id=session_id,
            options=result.get("options"),
            traces=[],
        )

    _chat_sessions.pop(session_id, None)

    if action == "ready":
        from app.services.engine import LaboralEngine

        params = result.get("params", {})
        try:
            convenio_data = _load_convenio_safe(convenio_id)
            engine = LaboralEngine(convenio_data)
            sim_result = engine.simulate(
                category=params.get("category", ""),
                contract_type=params.get("contract_type", "indefinido"),
                weekly_hours=params.get("weekly_hours", 40.0),
                seniority_years=params.get("seniority_years", 0),
                num_children=params.get("num_children", 0),
                children_under_3=params.get("children_under_3", 0),
                region=params.get("region", "generica"),
            )
        except Exception as exc:
            return ChatResponse(
                response=f"Error en simulacion: {exc}",
                traces=[],
                session_id=session_id,
            )

        sim_result["contract_extras"] = result.get("contract_extras", {})
        sim_result["contract_warnings"] = result.get("contract_warnings", [])

        from app.models.consultation import Consultation

        consultation = Consultation(
            user_id=current_user.id,
            query_summary=data.message[:200],
            request_data=data.model_dump_json(),
            result_data=json.dumps(sim_result, ensure_ascii=False, default=str),
        )
        db.add(consultation)
        db.commit()

        return ChatResponse(
            response="Simulacion completada",
            simulation=sim_result,
            traces=sim_result.get("traces", []),
            session_id=session_id,
        )

    if action == "budget_search":
        from app.services.engine import LaboralEngine

        params = result.get("params", {})
        try:
            convenio_data = _load_convenio_safe(convenio_id)
            engine = LaboralEngine(convenio_data)
            if hasattr(engine, "find_contracts_by_budget"):
                budget_result = engine.find_contracts_by_budget(**params)
            else:
                budget_result = {
                    "message": "Busqueda por presupuesto no disponible",
                    "params": params,
                }
        except Exception as exc:
            budget_result = {"error": str(exc)}

        return ChatResponse(
            response=json.dumps(budget_result, ensure_ascii=False, default=str),
            traces=[],
            session_id=session_id,
        )

    return ChatResponse(
        response=result.get("message", "No he podido identificar la categoria profesional."),
        traces=[],
        session_id=session_id,
    )


@router.post("/reset")
def reset_chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    if data.session_id:
        _chat_sessions.pop(data.session_id, None)
    return {"ok": True}
