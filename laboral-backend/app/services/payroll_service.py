from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.engine import LaboralEngine
from app.services.ss_calculator import SSCalculator
from app.services.irpf_estimator import IRPFEstimator

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _REPO_ROOT / "data"


def _load_convenio(convenio_id: str) -> dict[str, Any]:
    path = _DATA_DIR / f"{convenio_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Convenio no encontrado: {convenio_id}")
    import json

    return json.loads(path.read_text(encoding="utf-8"))


class PayrollService:
    def generate_nomina(
        self,
        category: str,
        contract_type: str,
        weekly_hours: float,
        region: str,
        num_children: int = 0,
        seniority_years: int = 0,
        convenio_id: str | None = None,
        contract_days: int | None = None,
    ) -> dict[str, Any]:
        if convenio_id is None:
            convenio_id = "convenio_acuaticas_2025_2027"

        data = _load_convenio(convenio_id)
        engine = LaboralEngine(data)
        result = engine.simulate(
            category=category,
            contract_type=contract_type,
            weekly_hours=weekly_hours,
            seniority_years=seniority_years,
            num_children=num_children,
            region=region,
            contract_days=contract_days,
        )
        return result

    def bulk_payroll(self, employees: list[dict], convenio_id: str, periodo: str) -> list[dict]:
        data = _load_convenio(convenio_id)
        engine = LaboralEngine(data)
        results = []
        for emp in employees:
            result = engine.simulate(
                category=emp.get("categoria", ""),
                contract_type=emp.get("contrato_tipo", "indefinido"),
                weekly_hours=emp.get("jornada_horas", 40.0),
                num_children=emp.get("num_hijos", 0),
                region=emp.get("region", "generica"),
            )
            result["employee_id"] = emp.get("id")
            result["employee_name"] = emp.get("nombre", "")
            result["periodo"] = periodo
            results.append(result)
        return results
