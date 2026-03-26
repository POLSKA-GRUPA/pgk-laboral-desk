"""
PGK Laboral Desk — Input Validation Layer

Centralized validation for simulation parameters, employee data, and API inputs.
Inspired by Karpathy's pattern of explicit parameter control and clear error messages.
"""

from __future__ import annotations

from exceptions import ValidationError

# Valid ranges for domain parameters
MIN_WEEKLY_HOURS = 1.0
MAX_WEEKLY_HOURS = 40.0
MIN_SALARY = 0.0
MAX_SALARY = 100_000.0  # Monthly salary cap (sanity check)
MAX_SENIORITY_YEARS = 60
MAX_CHILDREN = 20
VALID_CONTRACT_TYPES = {
    "indefinido",
    "temporal",
    "fijo-discontinuo",
    "temporal-produccion",
    "sustitucion",
    "tiempo-parcial",
}
VALID_DESPIDO_TYPES = {
    "improcedente",
    "objetivo",
    "colectivo",
    "disciplinario",
    "voluntario",
    "fin-contrato-temporal",
    "desistimiento-periodo-prueba",
}


def validate_simulation_params(
    category: str,
    contract_type: str = "indefinido",
    weekly_hours: float = 40.0,
    seniority_years: int = 0,
    num_children: int = 0,
    children_under_3: int = 0,
    contract_days: int | None = None,
) -> None:
    """Validate simulation parameters. Raises ValidationError on invalid input."""
    if not category or not category.strip():
        raise ValidationError(
            "Selecciona una categoria profesional",
            field="category",
        )

    if contract_type not in VALID_CONTRACT_TYPES:
        raise ValidationError(
            f"Tipo de contrato no valido: {contract_type}. "
            f"Opciones: {', '.join(sorted(VALID_CONTRACT_TYPES))}",
            field="contract_type",
        )

    if not MIN_WEEKLY_HOURS <= weekly_hours <= MAX_WEEKLY_HOURS:
        raise ValidationError(
            f"Horas semanales fuera de rango: {weekly_hours}. "
            f"Rango valido: {MIN_WEEKLY_HOURS}-{MAX_WEEKLY_HOURS}",
            field="weekly_hours",
        )

    if not 0 <= seniority_years <= MAX_SENIORITY_YEARS:
        raise ValidationError(
            f"Antiguedad fuera de rango: {seniority_years} anos",
            field="seniority_years",
        )

    if num_children < 0 or num_children > MAX_CHILDREN:
        raise ValidationError(
            f"Numero de hijos fuera de rango: {num_children}",
            field="num_children",
        )

    if children_under_3 < 0 or children_under_3 > num_children:
        raise ValidationError(
            f"Hijos menores de 3 ({children_under_3}) no puede superar total ({num_children})",
            field="children_under_3",
        )

    if contract_days is not None and contract_days < 1:
        raise ValidationError(
            f"Dias de contrato debe ser >= 1, recibido: {contract_days}",
            field="contract_days",
        )


def validate_salary(salary: float, field_name: str = "salario_bruto_mensual") -> None:
    """Validate a salary value."""
    if salary < MIN_SALARY:
        raise ValidationError(
            f"Salario no puede ser negativo: {salary}",
            field=field_name,
        )
    if salary > MAX_SALARY:
        raise ValidationError(
            f"Salario mensual fuera de rango: {salary} EUR (max: {MAX_SALARY})",
            field=field_name,
        )


def validate_date_iso(date_str: str, field_name: str = "fecha") -> None:
    """Validate a date string in ISO format (YYYY-MM-DD)."""
    import re

    if not date_str or not date_str.strip():
        raise ValidationError(
            f"Fecha requerida: {field_name}",
            field=field_name,
        )
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str.strip()):
        raise ValidationError(
            f"Formato de fecha invalido: {date_str}. Use YYYY-MM-DD",
            field=field_name,
        )
    # Validate it actually parses
    from datetime import date

    try:
        date.fromisoformat(date_str.strip())
    except ValueError as exc:
        raise ValidationError(
            f"Fecha invalida: {date_str}",
            field=field_name,
        ) from exc


def validate_despido_params(
    tipo_despido: str,
    fecha_inicio: str,
    salario_bruto_mensual: float,
) -> None:
    """Validate dismissal calculation parameters."""
    if tipo_despido not in VALID_DESPIDO_TYPES:
        raise ValidationError(
            f"Tipo de despido no valido: {tipo_despido}. "
            f"Opciones: {', '.join(sorted(VALID_DESPIDO_TYPES))}",
            field="tipo_despido",
        )
    validate_date_iso(fecha_inicio, "fecha_inicio")
    validate_salary(salario_bruto_mensual)


def validate_employee_data(
    nombre: str,
    categoria: str,
    fecha_inicio: str,
) -> None:
    """Validate employee creation data."""
    if not nombre or not nombre.strip():
        raise ValidationError("Nombre del trabajador requerido", field="nombre")
    if not categoria or not categoria.strip():
        raise ValidationError("Categoria profesional requerida", field="categoria")
    validate_date_iso(fecha_inicio, "fecha_inicio")
