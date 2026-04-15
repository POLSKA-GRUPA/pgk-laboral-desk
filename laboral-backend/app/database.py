"""Database configuration and session management."""

import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

connect_args = {}
if settings.is_sqlite:
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, echo=settings.DEBUG)

if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and seed default data."""
    from app.models import (  # noqa: F401
        alert,
        company,
        consultation,
        contract,
        convenio,
        dismissal,
        employee,
        payroll,
        user,
    )

    Base.metadata.create_all(bind=engine)
    _seed_default_data()


def _seed_default_data():
    """Seed default admin user if it doesn't exist."""
    from app.core.security import get_password_hash
    from app.models.user import User

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "pgk").first()
        if not admin:
            admin = User(
                username="pgk",
                hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD or "pgk2025"),
                full_name="PGK Hispania",
                empresa_nombre="PGK Hispania",
                role="admin",
                is_active=True,
                is_superuser=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin user 'pgk' created")
    finally:
        db.close()
