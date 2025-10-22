"""
FastAPI middleware components.

Contains authentication and API key validation middleware.
"""

from .auth import api_key_header, get_api_key

__all__ = ["api_key_header", "get_api_key"]
