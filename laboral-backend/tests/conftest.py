import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_laboral.db")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "testpass")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
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

test_engine = sa_create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    from app.core.security import get_password_hash
    from app.models.user import User

    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    try:
        if not db.query(User).filter(User.username == "pgk").first():
            admin = User(
                username="pgk",
                hashed_password=get_password_hash("testpass"),
                full_name="PGK Hispania",
                empresa_nombre="PGK Hispania",
                role="admin",
                is_active=True,
                is_superuser=True,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    resp = client.post("/api/auth/login", json={"username": "pgk", "password": "testpass"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
