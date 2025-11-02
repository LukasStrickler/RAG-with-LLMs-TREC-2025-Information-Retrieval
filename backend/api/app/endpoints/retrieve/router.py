"""
Retrieval endpoint.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

# Import shared models
from shared import (
    RetrievalRequest,
    RetrievalResponse,
)

from app.middleware.auth import get_api_key

router = APIRouter()


@router.post(
    "/retrieve",
    response_model=RetrievalResponse,
    summary="Document Retrieval",
    description="Simple document retrieval endpoint",
    response_description="Ranked retrieval results with metadata and diagnostics",
)
async def retrieve(
    app_request: Request,
    request: RetrievalRequest,
    api_key: str = Depends(get_api_key),
) -> RetrievalResponse:
    """
    Retrieve documents for given queries using specified retrieval mode.

    TODO: REPLACE WITH REAL RETRIEVAL IMPLEMENTATION
    Currently returns mock data for development/testing.
    When implementing:
    - Connect to actual BM25 index for lexical mode
    - Connect to vector store for semantic mode
    - Implement fusion logic for hybrid mode
    - Use real document retrieval and scoring

    Args:
        app_request: FastAPI request object to access app state
        request: RetrievalRequest with mode and queries
        api_key: API key for authentication

    Returns:
        RetrievalResponse: Contains ranked results for each query with diagnostics

    Raises:
        HTTPException: 503 if retrieval service is not available
    """

    # TODO: Replace with real retrieval service
    # This is currently using mock data for development/testing
    mock_service = getattr(app_request.app.state, "mock_service", None)
    if not mock_service:
        raise HTTPException(
            status_code=503,
            detail="Retrieval service not available. Please contact administrator.",
        )

    # Generate mock results for each query
    results = []
    for query in request.queries:
        result = mock_service.generate_response(
            query_id=query.query_id,
            query_text=query.query_text,
            top_k=query.top_k,
            mode=request.mode,  # Use the mode from the request
        )
        results.append(result)

    # Create response with API's own configuration
    # TODO: Replace hardcoded values with database calls when
    # implementing real retrieval
    # - schema_version: fetch from DB/config table
    # - dataset_version: fetch from active dataset configuration
    # - config_hash: compute from actual config state or fetch from DB
    response = RetrievalResponse(
        schema_version="1.0",  # TODO: Replace with DB call
        dataset_version="trec_rag_2024",  # TODO: Replace with DB call
        config_hash=(f"{request.mode}_config_v1"),  # TODO: Replace with DB call or hash
        request_id=str(uuid.uuid4()),
        results=results,
    )

    return response
