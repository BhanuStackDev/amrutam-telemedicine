from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Amrutam Telemedicine API"
    app_env: str = "development"
    debug: bool = False

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")

    access_token_expire_minutes: int = Field(
        15,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        ge=5,
        le=60,
    )

    refresh_token_expire_days: int = Field(
        30,
        alias="REFRESH_TOKEN_EXPIRE_DAYS",
        ge=1,
        le=365,
    )

    # Login security
    max_failed_login_attempts: int = Field(
        5,
        alias="MAX_FAILED_LOGIN_ATTEMPTS",
        ge=3,
        le=20,
    )

    account_lockout_minutes: int = Field(
        15,
        alias="ACCOUNT_LOCKOUT_MINUTES",
        ge=1,
        le=1440,
    )

    # MFA / TOTP secret encryption
    mfa_encryption_key: str = Field(
        ...,
        alias="MFA_ENCRYPTION_KEY",
    )

    cors_origins: str = Field(
        "",
        alias="CORS_ORIGINS",
    )

    otel_enabled: bool = Field(
        False,
        alias="OTEL_ENABLED",
    )

    otel_service_name: str = Field(
        "amrutam-telemedicine-api",
        alias="OTEL_SERVICE_NAME",
    )

    otel_exporter_otlp_endpoint: str = Field(
        "http://localhost:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    rate_limit_enabled: bool = Field(
        True,
        alias="RATE_LIMIT_ENABLED",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()