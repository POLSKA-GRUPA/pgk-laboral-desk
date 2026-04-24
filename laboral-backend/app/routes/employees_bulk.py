"""Alta masiva de empleados desde CSV.

Endpoints:
- GET  /api/employees/bulk-import/template  → devuelve plantilla CSV vacía.
- POST /api/employees/bulk-import            → valida + crea en lote.
  - `?dry_run=true` (default): sólo valida y devuelve errores por fila, no toca DB.
  - `?dry_run=false`: crea empleados si todas las filas son válidas; si hay
    errores en cualquier fila, no crea ninguno (all-or-nothing).

Validaciones por fila:
- Campos obligatorios: nombre, categoria, fecha_inicio (ISO YYYY-MM-DD).
- NIF/NIE/CIF si viene: dígito de control correcto (services/validators.py).
- NAF si viene: 12 dígitos con módulo 97 correcto.
- codigo_contrato_sepe si viene: código SEPE conocido (tabla sepe_code_tables).
- fecha_nacimiento si viene: ISO YYYY-MM-DD.
- Duplicado NIF dentro del propio fichero: rechazo.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.employee import Employee
from app.models.user import User
from app.schemas.employee import BulkImportError, BulkImportResult, BulkImportRow
from app.services.sepe_code_tables import CONTRACT_TYPES
from app.services.validators import (
    normalize_naf,
    normalize_nif,
    validate_naf,
    validate_nif,
)

router = APIRouter(prefix="/employees/bulk-import", tags=["employees"])

# Columnas de la plantilla CSV en orden canónico.
TEMPLATE_COLUMNS = [
    "nombre",
    "nif",
    "naf",
    "categoria",
    "contrato_tipo",
    "codigo_contrato_sepe",
    "jornada_horas",
    "fecha_inicio",
    "fecha_fin",
    "salario_bruto_mensual",
    "num_hijos",
    "region",
    "domicilio",
    "email",
    "telefono",
    "sexo",
    "fecha_nacimiento",
    "nacionalidad",
    "municipio_residencia",
    "pais_residencia",
    "temporada",
    "notas",
]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_VALID_CONTRATO_TIPOS = {
    "indefinido",
    "temporal",
    "fijo-discontinuo",
    "tiempo-parcial",
    "formacion",
    "practicas",
    "obra",
    "eventual",
    "interinidad",
    "relevo",
}


@router.get("/template")
def download_template(
    current_user: User = Depends(get_current_user),
) -> Response:
    """Devuelve la plantilla CSV vacía (sólo cabecera)."""
    header = ",".join(TEMPLATE_COLUMNS) + "\n"
    sample = (
        "Juan Pérez,12345678Z,281234567890,Peón agrícola,fijo-discontinuo,300,"
        "40,2026-05-01,,1200,0,generica,,,,1,1990-03-15,724,28079,724,"
        "Temporada-2026-V-Campaña-fresa,\n"
    )
    csv_content = header + sample
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="plantilla_bulk_import.csv"',
        },
    )


def _parse_csv(raw: bytes) -> list[dict[str, Any]]:
    """Lee CSV a lista de dicts. Admite UTF-8 con o sin BOM."""
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV vacío o mal formado")
    unknown = set(reader.fieldnames) - set(TEMPLATE_COLUMNS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Columnas desconocidas en CSV: {sorted(unknown)}",
        )
    return list(reader)


def _validate_row(
    row_index: int, raw: dict[str, Any]
) -> tuple[BulkImportRow | None, list[BulkImportError]]:
    """Devuelve la fila validada y coerced, o None + lista de errores."""
    errors: list[BulkImportError] = []

    def err(field: str, value: Any, message: str) -> None:
        errors.append(
            BulkImportError(
                row=row_index,
                field=field,
                value=str(value) if value is not None else "",
                message=message,
            )
        )

    cleaned: dict[str, Any] = {}
    for col in TEMPLATE_COLUMNS:
        cleaned[col] = (raw.get(col) or "").strip()

    # Obligatorios.
    for req in ("nombre", "categoria", "fecha_inicio"):
        if not cleaned[req]:
            err(req, cleaned[req], f"{req} es obligatorio")

    # Fechas ISO.
    for datefield in ("fecha_inicio", "fecha_fin", "fecha_nacimiento"):
        v = cleaned[datefield]
        if v and not _DATE_RE.fullmatch(v):
            err(datefield, v, "formato inválido, esperado YYYY-MM-DD")

    # NIF / NIE / CIF con checkdigit.
    nif = cleaned["nif"]
    if nif:
        normalized = normalize_nif(nif)
        if not validate_nif(normalized):
            err("nif", nif, "dígito de control incorrecto")
        cleaned["nif"] = normalized

    # NAF.
    naf = cleaned["naf"]
    if naf:
        normalized = normalize_naf(naf)
        if not validate_naf(normalized):
            err("naf", naf, "NAF inválido (12 dígitos con módulo 97)")
        cleaned["naf"] = normalized

    # contrato_tipo.
    ct = cleaned["contrato_tipo"] or "indefinido"
    if ct not in _VALID_CONTRATO_TIPOS:
        err("contrato_tipo", ct, f"tipo desconocido; válidos: {sorted(_VALID_CONTRATO_TIPOS)}")
    cleaned["contrato_tipo"] = ct

    # codigo_contrato_sepe.
    sepe_code = cleaned["codigo_contrato_sepe"]
    if sepe_code and sepe_code not in CONTRACT_TYPES:
        err("codigo_contrato_sepe", sepe_code, "código SEPE desconocido (ver tabla)")

    # Numéricos.
    def to_float(field: str, default: float | None = None) -> float | None:
        v = cleaned[field]
        if not v:
            return default
        try:
            return float(v.replace(",", "."))
        except ValueError:
            err(field, v, "no es numérico")
            return default

    def to_int(field: str, default: int = 0) -> int:
        v = cleaned[field]
        if not v:
            return default
        try:
            return int(v)
        except ValueError:
            err(field, v, "no es entero")
            return default

    jornada = to_float("jornada_horas", 40.0) or 40.0
    if not (1.0 <= jornada <= 40.0):
        err("jornada_horas", jornada, "debe estar entre 1 y 40")

    salario = to_float("salario_bruto_mensual", None)
    if salario is not None and not (0 < salario <= 100000):
        err("salario_bruto_mensual", salario, "debe estar entre 0 y 100000")

    num_hijos = to_int("num_hijos", 0)
    if not (0 <= num_hijos <= 20):
        err("num_hijos", num_hijos, "debe estar entre 0 y 20")

    if errors:
        return None, errors

    row = BulkImportRow(
        nombre=cleaned["nombre"],
        nif=cleaned["nif"],
        naf=cleaned["naf"],
        categoria=cleaned["categoria"],
        contrato_tipo=cleaned["contrato_tipo"],
        codigo_contrato_sepe=cleaned["codigo_contrato_sepe"],
        jornada_horas=jornada,
        fecha_inicio=cleaned["fecha_inicio"],
        fecha_fin=cleaned["fecha_fin"] or None,
        salario_bruto_mensual=salario,
        num_hijos=num_hijos,
        region=cleaned["region"] or "generica",
        domicilio=cleaned["domicilio"],
        email=cleaned["email"],
        telefono=cleaned["telefono"],
        sexo=cleaned["sexo"] or "1",
        fecha_nacimiento=cleaned["fecha_nacimiento"],
        nacionalidad=cleaned["nacionalidad"] or "724",
        municipio_residencia=cleaned["municipio_residencia"],
        pais_residencia=cleaned["pais_residencia"] or "724",
        temporada=cleaned["temporada"],
        notas=cleaned["notas"],
    )
    return row, []


@router.post("", response_model=BulkImportResult)
async def bulk_import(
    file: UploadFile,
    dry_run: bool = Query(True, description="Si true (default), sólo valida sin escribir"),
    company_id: int | None = Query(None, description="Asignar todas las filas a esta empresa"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BulkImportResult:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Fichero vacío")

    rows = _parse_csv(raw)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV sin filas de datos")

    valid: list[BulkImportRow] = []
    errors: list[BulkImportError] = []
    nifs_seen: dict[str, int] = {}

    for i, raw_row in enumerate(rows, start=2):  # fila 1 es cabecera
        parsed, row_errors = _validate_row(i, raw_row)
        if row_errors:
            errors.extend(row_errors)
            continue
        assert parsed is not None
        # Duplicado de NIF dentro del mismo fichero.
        if parsed.nif:
            if parsed.nif in nifs_seen:
                errors.append(
                    BulkImportError(
                        row=i,
                        field="nif",
                        value=parsed.nif,
                        message=f"NIF duplicado en fila {nifs_seen[parsed.nif]}",
                    )
                )
                continue
            nifs_seen[parsed.nif] = i
        valid.append(parsed)

    created_ids: list[int] = []
    if not dry_run and not errors:
        for row in valid:
            emp = Employee(
                user_id=current_user.id,
                company_id=company_id,
                nombre=row.nombre,
                nif=row.nif,
                naf=row.naf,
                categoria=row.categoria,
                contrato_tipo=row.contrato_tipo,
                codigo_contrato_sepe=row.codigo_contrato_sepe,
                jornada_horas=row.jornada_horas,
                fecha_inicio=row.fecha_inicio,
                fecha_fin=row.fecha_fin,
                salario_bruto_mensual=row.salario_bruto_mensual,
                num_hijos=row.num_hijos,
                region=row.region,
                domicilio=row.domicilio,
                email=row.email,
                telefono=row.telefono,
                sexo=row.sexo,
                fecha_nacimiento=row.fecha_nacimiento,
                nacionalidad=row.nacionalidad,
                municipio_residencia=row.municipio_residencia,
                pais_residencia=row.pais_residencia,
                temporada=row.temporada,
                notas=row.notas,
                status="activo",
            )
            db.add(emp)
            db.flush()
            created_ids.append(emp.id)
        db.commit()

    return BulkImportResult(
        total_rows=len(rows),
        valid_rows=len(valid),
        invalid_rows=len(rows) - len(valid),
        dry_run=dry_run or bool(errors),
        created=len(created_ids),
        errors=errors,
        created_ids=created_ids,
    )
