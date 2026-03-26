"""
PGK Laboral Desk — Custom Exception Hierarchy

Structured exceptions for clear error handling across the labor desk system.
Inspired by Karpathy's pattern of explicit, specific error types.
"""

from __future__ import annotations


class LaboralBaseError(Exception):
    """Base exception for all Laboral Desk errors."""

    def __init__(self, message: str, *, code: str = "LABORAL_ERROR", details: str = "") -> None:
        self.code = code
        self.details = details
        super().__init__(message)


class ValidationError(LaboralBaseError):
    """Input validation errors (invalid salary, hours, dates, etc.)."""

    def __init__(self, message: str, *, field: str = "", details: str = "") -> None:
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class EngineError(LaboralBaseError):
    """Errors in the calculation engine (missing data, impossible calculations)."""

    def __init__(self, message: str, *, details: str = "") -> None:
        super().__init__(message, code="ENGINE_ERROR", details=details)


class ConvenioNotFoundError(LaboralBaseError):
    """Requested convenio colectivo not found."""

    def __init__(self, convenio_id: str) -> None:
        self.convenio_id = convenio_id
        super().__init__(
            f"Convenio no encontrado: {convenio_id}",
            code="CONVENIO_NOT_FOUND",
            details=convenio_id,
        )


class AuthenticationError(LaboralBaseError):
    """Authentication or authorization errors."""

    def __init__(self, message: str = "No autenticado", *, details: str = "") -> None:
        super().__init__(message, code="AUTH_ERROR", details=details)


class DatabaseError(LaboralBaseError):
    """Database operation errors."""

    def __init__(self, message: str, *, details: str = "") -> None:
        super().__init__(message, code="DATABASE_ERROR", details=details)
