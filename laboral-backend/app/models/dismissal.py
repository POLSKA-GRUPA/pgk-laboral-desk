from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Dismissal(Base):
    __tablename__ = "dismissals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    tipo_despido: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha_inicio: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_extincion: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    salario_bruto_mensual: Mapped[float] = mapped_column(Float, nullable=False)
    indemnizacion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    datos_calculo: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
