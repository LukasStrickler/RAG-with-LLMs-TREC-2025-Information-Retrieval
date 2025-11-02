"""
FastAPI application configuration.
"""

import os
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

    # Fallback: validate fallback path
    fallback_path = Path(__file__).parent.parent.parent
    if (fallback_path / "shared").exists() and (fallback_path / "backend").exists():
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Using fallback project root: {fallback_path}. "
            "Consider setting PROJECT_ROOT environment variable explicitly."
        )
        return fallback_path

    # If fallback also invalid, raise exception
    raise RuntimeError(
        f"Could not find project root. Expected directory structure with 'shared/' and 'backend/' "
        f"subdirectories. Searched up from: {Path(__file__).parent}"
    )


def _get_default_qrels_path() -> Path:
    """Get default qrels path, checking QRELS_PATH env var first."""
    if qrels_env := os.getenv("QRELS_PATH"):
        qrels_path = Path(qrels_env)
        if not qrels_path.exists():
            raise FileNotFoundError(
                f"Qrels file from QRELS_PATH does not exist: {qrels_path}"
            )
        if not qrels_path.is_file():
            raise RuntimeError(f"Qrels path from QRELS_PATH is not a file: {qrels_path}")
        if not os.access(qrels_path, os.R_OK):
            raise RuntimeError(f"Qrels file from QRELS_PATH is not readable: {qrels_path}")
        return qrels_path

    project_root = _find_project_root()
    default_path = (
        project_root / ".data" / "trec_rag_assets" / "qrels.rag24.test-umbrela-all.txt"
    )

    if not default_path.exists():
        raise FileNotFoundError(
            f"Default qrels file not found: {default_path}. "
            f"Please set QRELS_PATH environment variable or ensure the file exists."
        )
    if not default_path.is_file():
        raise RuntimeError(f"Default qrels path is not a file: {default_path}")
    if not os.access(default_path, os.R_OK):
        raise RuntimeError(f"Default qrels file is not readable: {default_path}")

    return default_path


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
        env_file=str(Path(__file__).resolve().parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


try:
    # Validate .env file exists before loading settings
    env_file_path = Path(__file__).resolve().parent / ".env"
    if not env_file_path.exists():
        raise FileNotFoundError(
            f"Environment file not found: {env_file_path}. "
            f"Please ensure backend/api/.env exists. See backend/api/.env.example for template."
        )
    settings = Settings()
except FileNotFoundError as e:
    sys.stderr.write(f"{e}\n")
    sys.exit(1)
except Exception as e:
    sys.stderr.write(
        f"Configuration Error: {e}\n"
        f"Please check backend/api/.env and backend/api/.env.example\n"
        f"Ensure API_KEY and other required variables are set.\n"
    )
    sys.exit(1)
