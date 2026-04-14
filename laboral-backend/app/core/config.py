"""Application configuration using pydantic-settings."""

import os

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "PGK Laboral Desk"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False

    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str = ""
    CORS_ORIGINS: str = "http://localhost:5173"
    RATE_LIMIT_PER_MINUTE: int = 60

    DEFAULT_ADMIN_USERNAME: str = "pgk"
    DEFAULT_ADMIN_PASSWORD: str = ""

    ZAI_API_KEY: str = ""
    ZAI_BASE_URL: str = "https://z.ai"
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""

    BOE_API_BASE_URL: str = "https://boe.es/datosabiertos/api"
    ENVIRONMENT: str = "development"

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def set_secret_key(cls, v: str) -> str:
        if not v:
            import logging
            import secrets

            generated = secrets.token_hex(32)
            logging.getLogger(__name__).warning(
                "SECRET_KEY not set -- auto-generated for this session."
            )
            return generated
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self):
        is_deployed = bool(os.environ.get("FLY_APP_NAME") or self.ENVIRONMENT == "production")
        if is_deployed and not os.environ.get("SECRET_KEY"):
            raise ValueError("SECRET_KEY must be explicitly set in production.")
        return self

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def set_database_url(cls, v: str) -> str:
        if not v:
            if os.path.isdir("/data"):
                return "sqlite:////data/laboral.db"
            return "sqlite:///./laboral.db"
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            if self.ENVIRONMENT == "production":
                raise ValueError(
                    "CORS_ORIGINS='*' is not allowed with credentials in production. "
                    "Set explicit origins."
                )
            import logging

            logging.getLogger(__name__).warning(
                "CORS_ORIGINS='*' with allow_credentials=True is insecure. "
                "Set explicit origins for production."
            )
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
