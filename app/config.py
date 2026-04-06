"""
Application configuration via pydantic-settings.
Reads from .env file or environment variables.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Central configuration for TaskForge."""

    # ── Server ───────────────────────────────────────────
    port: int = Field(default=8080, description="Server port (Cloud Run sets PORT)")

    # ── Database ─────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://taskforge:taskforge@localhost:5432/taskforge",
        description="Async SQLAlchemy database URL",
    )

    # ── Gemini Auth (pick one) ───────────────────────────
    gemini_api_key: Optional[str] = Field(default=None, description="Gemini Developer API key")
    vertex_ai_project: Optional[str] = Field(default=None, description="GCP project ID for Vertex AI")
    vertex_ai_location: Optional[str] = Field(default="us-central1", description="GCP region")

    # ── Model ────────────────────────────────────────────
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model name")

    # ── Agent Settings ───────────────────────────────────
    max_agent_iterations: int = Field(default=10, description="Max tool-call loops per agent run")
    log_level: str = Field(default="INFO")

    # ── CORS ─────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins. Restrict to specific domains in production.",
    )

    @property
    def use_vertex_ai(self) -> bool:
        return self.vertex_ai_project is not None and self.gemini_api_key is None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton
settings = Settings()
