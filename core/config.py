from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://localhost:5432/framekatha"
    redis_url: str = "redis://localhost:6379/0"
    api_key: SecretStr
    default_phone_region: str = "IN"
    fuzzy_name_threshold: float = Field(default=92, ge=0, le=100)
    ingest_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_base_seconds: float = Field(default=0.25, ge=0, le=10)
    log_level: str = "INFO"

    @field_validator("api_key")
    @classmethod
    def validate_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 24:
            raise ValueError("API_KEY must contain at least 24 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg://")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
