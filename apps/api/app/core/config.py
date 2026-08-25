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
    actor_provider: str = "development"
    allow_development_actor_provider: bool = True
    session_cookie_name: str = "hiring_session"
    session_cookie_secure: bool = False
    session_ttl_hours: int = 12
    document_storage_root: str = ".hiring-documents"
    max_upload_bytes: int = 10 * 1024 * 1024
    screening_provider: str = "mock"
    screening_engine_root: str = "../hiring-screening-engine"
    screening_engine_timeout_seconds: int = 900
    screening_output_root: str = "screening-output"
    screening_engine_python: str = "python3"
    screening_worker_max_attempts: int = 1
    screening_chandra_base_url: str = "http://127.0.0.1:18083"
    screening_chandra_api_key: str | None = None
    screening_chandra_model: str = "chandra-ocr-2-q8"
    screening_gemma_base_url: str = "http://127.0.0.1:24181/v1"
    screening_gemma_fallback_base_url: str | None = None
    screening_gemma_api_key: str = "no-key"
    screening_gemma_model: str = "gemma4-12b"
    screening_gemma_resume_max_tokens: int = 16384
    screening_chandra_ocr_retry_max_tokens: int = 8192
    screening_pipeline_debug_raw_responses: bool = False
    vite_api_proxy_target: str = "http://localhost:8010"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="HIRING_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
