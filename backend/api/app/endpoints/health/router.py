"""
Health check endpoint.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

# Import shared models
from shared import HealthResponse

from app.config import settings

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the API is running and healthy",
    response_description="Current API status with version and timestamp",
)
def health_check() -> HealthResponse:
    """
    Health check endpoint for monitoring API status.

    This endpoint is used by monitoring systems and load balancers to verify
    that the API is running correctly. It returns the current status,
    API version, and timestamp.

    Returns:
        HealthResponse: Contains status, version, and timestamp
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
