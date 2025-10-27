"""
FastAPI application configuration.
"""

import sys
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """Find project root by looking for shared/ and backend/ directories."""
    current = Path(__file__).parent

    # Walk up directories looking for project root
    while current != current.parent:
        # Check if this is the main project root (has shared/ directory)
        if (current / "shared").exists() and (current / "backend").exists():
            return current
        current = current.parent

    # Fallback: return backend/api parent
    return Path(__file__).parent.parent.parent


def _get_default_qrels_path() -> Path:
    """Get default qrels path relative to project root."""
    project_root = _find_project_root()
    return (
        project_root / ".data" / "trec_rag_assets" / "qrels.rag24.test-umbrela-all.txt"
    )


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Server Configuration
    api_host: str = Field(default="0.0.0.0", description="API host address")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API port")
    api_key: SecretStr = Field(
        ..., min_length=32, description="API authentication key (minimum 32 characters)"
    )

    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], description="Allowed CORS origins"
    )

    # Data Configuration
    qrels_path: Path = Field(
        default_factory=_get_default_qrels_path,
        description="Path to qrels file for mock retrieval service",
    )

    # Application Metadata
    app_name: str = Field(
        default="RAG Retrieval API - TREC 2025", description="Application name"
    )
    app_version: str = Field(default="0.1.0", description="Application version")
    app_description: str = Field(
        default="Retrieval API for TREC 2025 Information Retrieval track",
        description="App description",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


try:
    settings = Settings()
except Exception as e:
    sys.stderr.write(
        f"Configuration Error: {e}\n"
        f"Please check backend/api/.env and backend/api/.env.example\n"
        f"Ensure API_KEY and other required variables are set.\n"
    )
    sys.exit(1)
