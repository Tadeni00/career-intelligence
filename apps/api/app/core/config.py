"""Application settings, loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # apps/api/app/core/config.py -> apps/api/app/core -> apps/api/app -> apps/api -> <root>
    return Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Career Intelligence API"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # --- database -----------------------------------------------------------
    database_url: str = "postgresql+psycopg://career:career@localhost:5433/career"

    # --- storage ------------------------------------------------------------
    storage_dir: Path = Field(default_factory=lambda: _repo_root() / "storage")
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_upload_extensions: tuple[str, ...] = (".pdf", ".docx")
    allowed_upload_mime_types: tuple[str, ...] = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",  # many clients send this for .docx
    )

    # --- AI provider --------------------------------------------------------
    # "openai"  -> real LLM calls via the OpenAI-compatible API
    # "offline" -> deterministic heuristic provider (no network, used by tests)
    ai_provider: Literal["openai", "offline"] = "offline"
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = 60.0
    ai_max_retries: int = 1

    # --- matching -----------------------------------------------------------
    match_weight_technical: float = 0.40
    match_weight_experience: float = 0.25
    match_weight_education: float = 0.10
    match_weight_location: float = 0.10
    match_weight_other: float = 0.15

    threshold_apply: float = 80.0
    threshold_apply_with_tailoring: float = 65.0
    threshold_stretch: float = 50.0

    # --- JSearch ------------------------------------------------------------
    # RapidAPI gateway contract, verified live 2026-10-13 (path /search-v2,
    # X-RapidAPI-Key / X-RapidAPI-Host auth). Overridable via env.
    jsearch_api_key: str = ""
    jsearch_base_url: str = "https://jsearch.p.rapidapi.com"
    jsearch_timeout_seconds: float = 15.0
    jsearch_max_retries: int = 1

    # --- Indeed.com Indeed API (alternative source, covers Benin Republic) ---
    indeed_base_url: str = "https://indeed.p.rapidapi.com"

    # --- candidate ----------------------------------------------------------
    # V1 is single-user: the profile resolved for every request.
    default_candidate_name: str = "Candidate"

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def generated_dir(self) -> Path:
        return self.storage_dir / "generated"

    def ensure_storage(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)



def require_supported_runtime(settings: Settings) -> None:
    """Fail closed until the API has authenticated user and ownership boundaries.

    The current single-candidate API is permitted only in development/test
    environments. Even a correctly configured production secret or DEBUG=false
    cannot make the unprotected record-ID routes safe to publish.
    """
    if settings.environment == "production":
        raise RuntimeError(
            "Career Intelligence production mode is disabled: "
            "authenticated sessions and per-record authorization are not implemented. "
            "Use trusted, loopback-only development mode until those controls exist."
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_storage()
    return settings
