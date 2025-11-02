"""
API key authentication middleware.
"""

import hmac

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

# API Key header configuration
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """
    Validate API key from X-API-Key header.

    This dependency function validates the API key provided in the X-API-Key header
    against the configured API key in settings. Used to protect endpoints that require
    authentication.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        str: The validated API key

    Raises:
        HTTPException: 500 if the server-side API key is not configured (with
            message: "API key not configured. Please contact administrator.")
        HTTPException: 401 if the provided X-API-Key is missing or invalid
            (with message: "Could not validate credentials. Please check your API key.")
    """
    # Validate that API key is configured
    if not settings.api_key.get_secret_value():
        raise HTTPException(
            status_code=500,
            detail="API key not configured. Please contact administrator.",
        )

    # Use hmac.compare_digest for timing-safe comparison to prevent timing attacks
    if api_key and hmac.compare_digest(api_key, settings.api_key.get_secret_value()):
        return api_key
    raise HTTPException(
        status_code=401,
        detail="Could not validate credentials. Please check your API key.",
    )
