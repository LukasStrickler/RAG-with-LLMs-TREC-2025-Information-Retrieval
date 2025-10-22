"""
Backend API response models and types.
"""

from pydantic import BaseModel

from shared.data import ChunkingSpec, DatasetSpec, IndexTarget


class MetadataResponse(BaseModel):
    """Metadata response containing all current configuration data."""

    dataset_spec: DatasetSpec
    chunking_spec: ChunkingSpec
    available_indexes: list[IndexTarget]
    schema_version: str


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = "healthy"
    version: str
    timestamp: str


class ApiInfoResponse(BaseModel):
    """API information response model."""

    message: str
    version: str
    description: str
    docs: dict[str, str]
    contact: dict[str, str]
