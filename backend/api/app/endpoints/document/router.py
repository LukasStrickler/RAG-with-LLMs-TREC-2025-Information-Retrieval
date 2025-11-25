"""
Document endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any

from app.middleware.auth import get_api_key

router = APIRouter()

@router.get(
    "/document/{doc_id}",
    response_model=Dict[str, Any],
    summary="Get Document",
    description="Retrieve full document content by ID",
)
async def get_document(
    doc_id: str,
    app_request: Request,
    api_key: str = Depends(get_api_key),
) -> Dict[str, Any]:
    """
    Retrieve a single document by ID.
    """
    retrieval_service = getattr(app_request.app.state, "retrieval_service", None)
    if not retrieval_service:
        raise HTTPException(
            status_code=503,
            detail="Retrieval service not available",
        )

    document = retrieval_service.get_document_by_id(doc_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found",
        )

    return document
