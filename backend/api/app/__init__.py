"""
FastAPI application main module.

This module provides the core FastAPI application instance and configuration
for the TREC 2025 Information Retrieval API. It includes:

- FastAPI app instance with CORS middleware
- Settings configuration from environment variables
- Endpoint routers for health, metadata, and retrieval
- API documentation and contact information

Public API:
- app: FastAPI application instance
- settings: Application configuration settings
"""

# Re-export key public entities
from app.config import settings
from app.main import app

__all__ = ["app", "settings"]
