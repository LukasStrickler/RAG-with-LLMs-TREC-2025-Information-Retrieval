"""
FastAPI application main module.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import shared models
from shared import ApiInfoResponse

from app.config import settings
from app.endpoints.health.router import router as health_router
from app.endpoints.metadata.router import router as metadata_router
from app.endpoints.retrieve.router import router as retrieve_router
from app.services.mock_retrieval import MockRetrievalService

# Configure logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Initializing retrieval service...")

    # Validate qrels file exists
    if not settings.qrels_path.exists():
        raise RuntimeError(
            f"Qrels file not found: {settings.qrels_path}\n"
            "Please ensure the qrels file exists or update "
            "QRELS_PATH in your configuration."
        )

    # Initialize mock retrieval service
    app.state.mock_service = MockRetrievalService(settings.qrels_path)
    logger.info(
        f"✓ Mock retrieval service initialized with qrels: {settings.qrels_path}"
    )

    yield

    # Shutdown (if needed in the future)
    logger.info("Shutting down retrieval service...")


# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    description="""
    API for the TREC 2025 Information Retrieval track, focusing on retrieval 
    capabilities. 
        
    This API provides endpoints for:
    - Health monitoring - Check API status
    - Metadata retrieval - Get dataset and index information  
    - Document retrieval - Unified endpoint for single and batch queries
    
    Retrieval endpoints support both lexical and semantic retrieval modes,
    with hybrid fusion capabilities for optimal performance.
    
    See architecture details in the project documentation (https://github.com/LukasStrickler/RAG-with-LLMs-TREC-2025-Information-Retrieval/tree/main/.docs).
    """,
    version=settings.app_version,
    lifespan=lifespan,
    contact={
        "name": "RAG Team - TREC 2025",
        "url": "https://github.com/LukasStrickler/RAG-with-LLMs-TREC-2025-Information-Retrieval",
    },
    license_info={"name": "MIT License", "url": "https://opensource.org/licenses/MIT"},
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# Include routers
app.include_router(health_router, tags=["health"])
app.include_router(retrieve_router, prefix="/api/v1", tags=["retrieval"])
app.include_router(metadata_router, prefix="/api/v1", tags=["metadata"])


@app.get(
    "/",
    response_model=ApiInfoResponse,
    summary="API Information",
    description="Get basic information about the RAG Retrieval API",
    response_description="API metadata and available documentation links",
)
async def root() -> ApiInfoResponse:
    """
    Root endpoint providing API information and documentation links.

    Returns basic metadata about the API including version and links to
    interactive documentation (Swagger UI and ReDoc).
    """
    return ApiInfoResponse(
        message="RAG Retrieval API - TREC 2025",
        version=settings.app_version,
        description="Retrieval API for TREC 2025 Information Retrieval track",
        docs={"swagger_ui": "/docs", "redoc": "/redoc", "openapi": "/openapi.json"},
        contact={
            "name": "RAG Team - TREC 2025",
            "url": "https://github.com/LukasStrickler/RAG-with-LLMs-TREC-2025-Information-Retrieval",
        },
    )
