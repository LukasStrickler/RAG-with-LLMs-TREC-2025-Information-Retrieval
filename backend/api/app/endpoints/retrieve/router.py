"""
Retrieval endpoint.
"""

import uuid

from fastapi import APIRouter, Depends

# Import shared models
from shared import (
    ProvenanceInfo,
    QueryResult,
    RetrievalDiagnostics,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedSegment,
    SegmentMetadata,
)
from shared.enums import IndexKind

from app.middleware.auth import get_api_key

router = APIRouter()


@router.post(
    "/retrieve",
    response_model=RetrievalResponse,
    summary="Document Retrieval",
    description=(
        "Unified endpoint for document retrieval supporting single and batch queries"
    ),
    response_description="Ranked retrieval results with metadata and diagnostics",
)
async def retrieve(request: RetrievalRequest, api_key: str = Depends(get_api_key)):
    """
    Retrieve documents for given queries using specified retrieval configuration.

    This is the main retrieval endpoint that supports:
    - **Single queries** - Process one query at a time
    - **Batch queries** - Process multiple queries in a single request
    - **Multiple retrieval modes** - Lexical (BM25), semantic (vector), and hybrid
    - **Configurable indexes** - Support for multiple index targets with weights

    The endpoint returns ranked results with detailed metadata, provenance information,
    and performance diagnostics for each query.

    Args:
        request: RetrievalRequest containing queries and configuration
        api_key: API key for authentication

    Returns:
        RetrievalResponse: Contains ranked results for each query with diagnostics

    Raises:
        HTTPException: If authentication fails or request validation fails
    """

    # TODO: Replace mock retrieval with service layer adapter
    # (config -> retrieval service -> BM25/vector stores)
    # Generate mock results for each query
    results = []
    for query in request.queries:
        # Create mock segments with realistic scores
        segments = []
        for i, score in enumerate([0.95, 0.87, 0.72]):
            segment = RetrievedSegment(
                segment_id=f"msmarco_doc_{i+1:02d}_{query.query_id}",
                score=score,
                metadata=SegmentMetadata(
                    title=f"Mock Document {i+1}",
                    url=f"https://example.com/doc{i+1}",
                    headings=[f"Section {i+1}"],
                    extras={"source": "mock"},
                ),
                provenance=ProvenanceInfo(
                    index_kind=IndexKind.HYBRID,
                    index_snapshot="mock_snapshot_001",
                    score_components={"lexical": score * 0.6, "semantic": score * 0.4},
                ),
            )
            segments.append(segment)

        # Create diagnostics with realistic performance metrics
        diagnostics = RetrievalDiagnostics(
            latency_ms=75.5,
            config_hash=request.config_hash,
            index_versions={"lexical": "v1.0", "vector": "v1.0"},
            warnings=[],
        )

        # Create query result
        result = QueryResult(
            query_id=query.query_id, segments=segments, diagnostics=diagnostics
        )
        results.append(result)

    # Create response with unique request ID
    response = RetrievalResponse(
        schema_version=request.schema_version,
        dataset_version=request.dataset_version,
        config_hash=request.config_hash,
        request_id=str(uuid.uuid4()),
        results=results,
    )

    return response
