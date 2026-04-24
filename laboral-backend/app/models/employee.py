from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    nif: Mapped[str] = mapped_column(String(20), default="")
    naf: Mapped[str] = mapped_column(String(20), default="")
    categoria: Mapped[str] = mapped_column(String(100), nullable=False)
    contrato_tipo: Mapped[str] = mapped_column(String(50), default="indefinido")
    jornada_horas: Mapped[float] = mapped_column(Float, default=40.0)
    fecha_inicio: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_fin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    salario_bruto_mensual: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_hijos: Mapped[int] = mapped_column(Integer, default=0)
    region: Mapped[str] = mapped_column(String(50), default="generica")
    domicilio: Mapped[str] = mapped_column(String(300), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    telefono: Mapped[str] = mapped_column(String(30), default="")
    sexo: Mapped[str] = mapped_column(String(1), default="1")
    fecha_nacimiento: Mapped[str] = mapped_column(String(20), default="")
    nacionalidad: Mapped[str] = mapped_column(String(3), default="724")
    municipio_residencia: Mapped[str] = mapped_column(String(5), default="")
    pais_residencia: Mapped[str] = mapped_column(String(3), default="724")
    notas: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="activo")

    # Campos fijo discontinuo (RDL 32/2021). El código SEPE (300/330/350)
    # convive con `contrato_tipo` por compatibilidad con el resto del v3.
    codigo_contrato_sepe: Mapped[str] = mapped_column(String(3), default="")
    fecha_llamamiento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fecha_cese_temporada: Mapped[str | None] = mapped_column(String(20), nullable=True)
    temporada: Mapped[str] = mapped_column(String(50), default="")
    estado_llamamiento: Mapped[str] = mapped_column(String(20), default="")
    dias_trabajados_temporada: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
