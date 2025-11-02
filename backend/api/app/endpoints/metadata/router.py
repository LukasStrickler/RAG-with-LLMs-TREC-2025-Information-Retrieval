"""
Metadata endpoint.
"""

from typing import Any

from fastapi import APIRouter, Depends

# Import shared models
from shared import (
    ChunkingSpec,
    DatasetSpec,
    IndexTarget,
    MetadataResponse,
)
from shared.enums import IndexKind

from app.middleware.auth import get_api_key

router = APIRouter()


@router.get(
    "/metadata",
    response_model=MetadataResponse,
    summary="Get Configuration Metadata",
    description=(
        "Retrieve all current configuration data including dataset, "
        "chunking, and index specifications"
    ),
    response_description="Complete configuration metadata from database",
)
async def get_metadata(api_key: str = Depends(get_api_key)) -> dict[str, Any]:
    """
    Get all current configuration metadata from the database.

    This endpoint provides comprehensive information about the current
    system configuration:
    - Dataset specification (name, version, split, etc.)
    - Chunking configuration (size, overlap, strategy)
    - Available indexes (lexical, vector, hybrid) with their specifications
    - Schema and dataset versions for compatibility

    Note: No request body or filtering is currently supported.
    Filtering criteria may be added in a future release.

    Args:
        api_key: API key for authentication

    Returns:
        MetadataResponse: Contains all configuration data

    Raises:
        HTTPException: If authentication fails

    TODO: Replace static responses with actual database queries
    """

    # TODO: Fetch from metadata DB (e.g. metadata.dataset_specs filled by
    # ingestion pipeline)
    # Mock dataset spec - in production this would come from database
    dataset_spec = DatasetSpec(
        name="MS MARCO v2.1",
        version="dev",
        split="dev",
        release_date="2024-01-01",
        source_uri="https://microsoft.github.io/msmarco/",
    )

    # TODO: Load from metadata DB (e.g. metadata.chunking_specs persisted by
    # ingestion jobs)
    # Mock chunking spec - in production this would come from database
    chunking_spec = ChunkingSpec(
        chunk_size=512, overlap=50, tokenizer="tiktoken", strategy="semantic_boundary"
    )

    # TODO: Query index registry (e.g. metadata.index_targets maintained by
    # index builders)
    # Mock available indexes - in production this would come from database
    available_indexes = [
        IndexTarget(
            kind=IndexKind.LEXICAL,
            uri="mock://lexical-index",
            snapshot_id="lexical_v1.0",
        ),
        IndexTarget(
            kind=IndexKind.VECTOR, uri="mock://vector-index", snapshot_id="vector_v1.0"
        ),
        IndexTarget(
            kind=IndexKind.HYBRID, uri="mock://hybrid-index", snapshot_id="hybrid_v1.0"
        ),
    ]

    return MetadataResponse(
        dataset_spec=dataset_spec,
        chunking_spec=chunking_spec,
        available_indexes=available_indexes,
        schema_version="1.0.0",
    )
