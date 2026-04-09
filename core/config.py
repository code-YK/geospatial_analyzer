"""
core/config.py — Application configuration using pydantic-settings.

All configuration is loaded from environment variables / .env file.
No hardcoded strings outside of this module and scoring/weights.py.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/geospatial_db"

    # ── LangGraph Checkpointer ────────────────────────────────────────────
    langgraph_checkpoint_url: str = "postgresql://user:password@localhost:5432/geospatial_db"

    # ── LLM ──────────────────────────────────────────────────────────────
    llm_provider: Literal["groq", "openai", "anthropic", "ollama"] = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1000
    groq_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ── App ──────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    h3_resolution: int = 8


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
