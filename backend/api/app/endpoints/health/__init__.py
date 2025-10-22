"""
Health monitoring and diagnostics endpoints.

Provides endpoints for API health checks, version information, and system status.
"""

from .router import router

__all__ = ["router"]
