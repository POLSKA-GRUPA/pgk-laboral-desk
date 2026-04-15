from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=4, max_length=200)
    full_name: str = Field(default="", max_length=200)
    empresa_nombre: str = Field(default="", max_length=200)
    empresa_cif: str = Field(default="", max_length=50)
    convenio_id: str = Field(default="", max_length=100)
    role: str = Field(default="client", pattern="^(admin|client)$")


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    empresa_nombre: str | None = Field(default=None, max_length=200)
    empresa_cif: str | None = Field(default=None, max_length=50)
    empresa_domicilio: str | None = Field(default=None, max_length=300)
    empresa_ccc: str | None = Field(default=None, max_length=50)
    full_name: str | None = Field(default=None, max_length=200)
    convenio_id: str | None = Field(default=None, max_length=100, pattern=r"^[a-zA-Z0-9_\-]*$")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    full_name: str
    empresa_nombre: str
    empresa_cif: str
    empresa_domicilio: str
    empresa_ccc: str
    convenio_id: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
