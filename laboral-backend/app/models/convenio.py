from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Convenio(Base):
    __tablename__ = "convenios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(300), nullable=False)
    codigo_convenio: Mapped[str] = mapped_column(String(50), unique=True, default="")
    ambito_geografico: Mapped[str] = mapped_column(String(200), default="")
    vigencia_inicio: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    vigencia_fin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sector: Mapped[str] = mapped_column(String(100), default="")
    data_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
