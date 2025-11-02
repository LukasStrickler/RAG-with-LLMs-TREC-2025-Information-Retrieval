"""
FastAPI application package public API.

This module serves as a consolidation and re-export point for the package public API,
exposing the main application instance and configuration settings.

Public API:
- app: FastAPI application instance
- settings: Application configuration settings
"""

# Re-export key public entities
from app.config import settings
from app.main import app

__all__ = ["app", "settings"]
