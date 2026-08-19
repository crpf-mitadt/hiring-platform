from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Hiring Platform"
    environment: str = "local"
    database_url: str = Field(
        default="postgresql+psycopg://hiring:hiring@localhost:5433/hiring_platform"
    )
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="HIRING_")


@lru_cache
def get_settings() -> Settings:
    return Settings()

