"""
Retrieval endpoint.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

# Import shared models
from shared import (
    RetrievalRequest,
    RetrievalResponse,
)

from app.middleware.auth import get_api_key

logger = logging.getLogger(__name__)
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

    logger.info(
        f"Received retrieval request: mode={request.mode}, "
        f"num_queries={len(request.queries)}, "
        f"top_k={request.queries[0].top_k if request.queries else 'N/A'}, "
        f"rerank={request.rerank}"
    )
    print(
        f"[DEBUG] Server: Received retrieval request: mode={request.mode}, num_queries={len(request.queries)}, rerank={request.rerank}"
    )

    # Access real retrieval service
    retrieval_service = getattr(app_request.app.state, "retrieval_service", None)
    if not retrieval_service:
        logger.error("Retrieval service not available")
        raise HTTPException(
            status_code=503,
            detail="Retrieval service not available. Please check server logs.",
        )

    # Generate results for each query with limited concurrency
    # Process in batches to avoid overwhelming the thread pool
    batch_size = 25  # Process 25 queries concurrently per batch
    logger.info(
        f"Processing {len(request.queries)} queries in batches of {batch_size}..."
    )
    print(
        f"[DEBUG] Server: Starting to process {len(request.queries)} queries in batches of {batch_size}"
    )

    results = []
    import time

    start_time = time.time()
    for i in range(0, len(request.queries), batch_size):
        batch = request.queries[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(request.queries) + batch_size - 1) // batch_size
        logger.info(
            f"Processing batch {batch_num}/{total_batches} ({len(batch)} queries)..."
        )
        print(
            f"[DEBUG] Server: Processing batch {batch_num}/{total_batches} ({len(batch)} queries)..."
        )
        batch_start = time.time()
        tasks = [
            retrieval_service.generate_response(
                query_id=query.query_id,
                query_text=query.query_text,
                top_k=query.top_k,
                mode=request.mode,  # Use the mode from the request
            )
            for query in batch
        ]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
        batch_time = time.time() - batch_start
        elapsed = time.time() - start_time
        logger.info(
            f"Completed batch {batch_num}/{total_batches} ({len(batch_results)} results) in {batch_time:.2f}s (total: {elapsed:.2f}s)"
        )
        print(
            f"[DEBUG] Server: Completed batch {batch_num}/{total_batches} in {batch_time:.2f}s (total elapsed: {elapsed:.2f}s)"
        )

    total_time = time.time() - start_time
    logger.info(
        f"Completed processing all {len(results)} query results in {total_time:.2f}s"
    )
    print(f"[DEBUG] Server: Completed all {len(results)} queries in {total_time:.2f}s")

    # Apply reranking if requested
    if request.rerank:
        print(f"[DEBUG] Server: Reranking requested, checking reranker availability...")
        reranker = getattr(app_request.app.state, "reranker", None)
        if reranker:
            print(f"[DEBUG] Server: Reranker is available")
            total_queries = len(results)
            total_segments = sum(len(r.segments) for r in results)
            logger.info(
                "🔄 Starting cross-encoder reranking for %d queries (%d total segments, mode=%s)",
                total_queries,
                total_segments,
                request.mode,
            )
            print(
                f"[DEBUG] Server: Starting reranking for {total_queries} queries ({total_segments} segments)"
            )
            rerank_start = time.time()
            reranked_results = []
            # Log progress more frequently for large batches
            log_interval = 5 if total_queries > 50 else 1
            for i, (result, query) in enumerate(
                zip(results, request.queries, strict=True), start=1
            ):
                query_start = time.time()
                if i % log_interval == 0 or i == 1 or i == total_queries:
                    logger.info(
                        "Reranking query %d/%d: %s (%d segments)",
                        i,
                        total_queries,
                        query.query_id,
                        len(result.segments),
                    )
                    print(
                        f"[DEBUG] Server: Reranking query {i}/{total_queries}: {query.query_id} ({len(result.segments)} segments)"
                    )
                reranked_result = reranker.rerank_query_result(
                    query_result=result, query_text=query.query_text
                )
                query_time = time.time() - query_start
                if i % log_interval == 0 or i == 1 or i == total_queries:
                    logger.info(
                        "Completed reranking query %d/%d: %s (%.2fs)",
                        i,
                        total_queries,
                        query.query_id,
                        query_time,
                    )
                reranked_results.append(reranked_result)
            rerank_time = time.time() - rerank_start
            logger.info(
                "✅ Reranking completed: %d queries reranked in %.2fs (avg: %.2fs/query)",
                len(reranked_results),
                rerank_time,
                rerank_time / len(reranked_results) if reranked_results else 0,
            )
            print(
                f"[DEBUG] Server: Reranking completed: {len(reranked_results)} queries in {rerank_time:.2f}s"
            )
            results = reranked_results
        else:
            logger.warning(
                "Reranking requested but reranker service not available. "
                "Returning original results."
            )
            print("[DEBUG] Server: ⚠️  Reranking requested but reranker not available - returning original results")

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
