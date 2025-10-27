"""
FastAPI application configuration.
"""

import sys
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default=Path("/Users/lukasstrickler/Desktop/Personal Projects/00 - University/RAG-with-LLMs-TREC-2025-Information-Retrieval/.data/trec_rag_assets/qrels.rag24.test-umbrela-all.txt"),
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
