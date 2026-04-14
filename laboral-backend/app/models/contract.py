from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha_inicio: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_fin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    jornada_horas: Mapped[float] = mapped_column(Float, default=40.0)
    categoria: Mapped[str] = mapped_column(String(100), default="")
    salario_pactado: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    observaciones: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
