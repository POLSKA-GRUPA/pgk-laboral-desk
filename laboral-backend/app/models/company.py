from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    cif: Mapped[str] = mapped_column(String(50), default="")
    domicilio: Mapped[str] = mapped_column(String(300), default="")
    ccc: Mapped[str] = mapped_column(String(50), default="")
    convenio_id: Mapped[str] = mapped_column(String(100), default="")
    sector: Mapped[str] = mapped_column(String(100), default="")
    regimen_cotizacion: Mapped[str] = mapped_column(String(4), default="0111")
    municipio_ct: Mapped[str] = mapped_column(String(5), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
