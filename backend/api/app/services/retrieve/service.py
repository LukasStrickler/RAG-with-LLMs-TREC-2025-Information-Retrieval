import asyncio
import json
import logging
import os
from typing import Any, Literal

import httpx
from shared.enums import IndexKind
from shared.retrieval.response import (
    ProvenanceInfo,
    QueryResult,
    RetrievalDiagnostics,
    RetrievedSegment,
    SegmentMetadata,
)

from app.config import settings

from .retrievers import (
    DatabaseRetriever,
    HybridRetriever,
    QdrantRetriever,
    SearchResult,
    SolrRetriever,
)
from .ssh_utils import SSHTunnelManager

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Real Retrieval Service implementation using Solr and Qdrant via SSH Tunnel.
    """

    def __init__(self):
        self.tunnel_manager = SSHTunnelManager()
        self.solr: SolrRetriever | None = None
        self.qdrant: QdrantRetriever | None = None
        self.hybrid: HybridRetriever | None = None
        self.db: DatabaseRetriever | None = None
        self.tunnel_active = False

    def startup(self):
        """Start SSH tunnel and initialize retrievers."""
        try:
            logger.info("Starting SSH tunnel...")
            ports = self.tunnel_manager.start()
            self.tunnel_active = True

            # Initialize Solr
            solr_core = os.getenv("SOLR_CORE", "small")
            # Solr is accessed via localhost through the tunnel
            solr_url = f"http://localhost:{ports['solr']}/solr"
            self.solr = SolrRetriever(solr_url, solr_core)
            logger.info(f"Solr initialized at {solr_url} (core: {solr_core})")

            # Initialize Qdrant with increased timeout for SSH tunnel
            qdrant_collection = settings.qdrant_collection or os.getenv(
                "QDRANT_COLLECTION", "documents"
            )
            qdrant_api_key = settings.qdrant_api_key or os.getenv("QDRANT_API_KEY")

            # Qdrant is accessed via localhost through the tunnel
            # Use longer timeout (120s) to handle SSH tunnel latency and large queries
            self.qdrant = QdrantRetriever(
                "localhost",
                ports["qdrant"],
                qdrant_collection,
                api_key=qdrant_api_key,
                timeout=120,
            )
            logger.info(
                f"Qdrant initialized at localhost:{ports['qdrant']} (collection: {qdrant_collection}, timeout: 120s)"
            )

            # Initialize Hybrid
            self.hybrid = HybridRetriever(self.solr, self.qdrant)
            logger.info("Hybrid retriever initialized")

            # Initialize Database Retriever
            db_name = os.getenv("DB_NAME", "postgres")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "")
            self.db = DatabaseRetriever(
                host="localhost",
                port=ports["db"],
                dbname=db_name,
                user=db_user,
                password=db_password,
            )
            logger.info(f"Database retriever initialized at localhost:{ports['db']}")

        except Exception as e:
            logger.error(f"Failed to startup RetrievalService: {e}")
            # If startup fails, we might want to re-raise or handle gracefully depending on app needs
            # For now, we'll log and re-raise to prevent app from starting in a broken state
            raise e

    def shutdown(self):
        """Stop SSH tunnel."""
        if self.tunnel_active:
            logger.info("Stopping SSH tunnel...")
            self.tunnel_manager.stop()
            self.tunnel_active = False

    async def generate_response(
        self,
        query_id: str,
        query_text: str,
        top_k: int = 100,
        mode: Literal["lexical", "vector", "hybrid"] = "hybrid",
    ) -> QueryResult:
        """Generate retrieval response for a single query."""

        if not self.tunnel_active:
            logger.error("RetrievalService is not active (tunnel down)")
            return QueryResult(
                query_id=query_id,
                segments=[],
                diagnostics=RetrievalDiagnostics(
                    latency_ms=0,
                    config_hash="error",
                    index_versions={},
                    warnings=["Service not active"],
                ),
            )

        try:
            results: list[SearchResult] = []

            # Only generate embedding for vector or hybrid modes
            query_vector = None
            if mode in ("vector", "hybrid"):
                query_vector = await self._get_query_vector(query_text)

            if mode == "lexical":
                if self.solr:
                    # Run blocking Solr search in thread pool
                    logger.debug(f"Searching Solr for query: {query_id}")
                    results = await asyncio.to_thread(
                        self.solr.search, query_text, top_k
                    )
                    logger.debug(
                        f"Solr returned {len(results)} results for query: {query_id}"
                    )
            elif mode == "vector":
                if self.qdrant and query_vector:
                    # Run blocking Qdrant search in thread pool
                    results = await asyncio.to_thread(
                        self.qdrant.search, query_vector, top_k
                    )
            elif mode == "hybrid" and self.hybrid and query_vector:
                # Run blocking hybrid search in thread pool
                results = await asyncio.to_thread(
                    self.hybrid.search, query_text, query_vector, top_k
                )

            # Fetch full document content from database
            doc_ids = [res.doc_id for res in results]
            db_docs = {}
            if self.db and doc_ids:
                logger.debug(
                    f"Fetching {len(doc_ids)} documents from database. Sample IDs: {doc_ids[:5]}"
                )
                # Run blocking DB query in thread pool
                db_docs = await asyncio.to_thread(self.db.get_documents, doc_ids)
                logger.debug(f"Fetched {len(db_docs)} documents from database")

            # Convert SearchResult to RetrievedSegment
            segments = []
            for i, res in enumerate(results):
                # Extract metadata
                meta = res.metadata or {}

                # Get full document from database
                db_doc = db_docs.get(res.doc_id, {})
                content = db_doc.get("body", res.content or "No content available")
                title = db_doc.get("title", meta.get("title", f"Document {res.doc_id}"))
                url = db_doc.get("url", meta.get("url", ""))

                # Determine IndexKind based on result source
                index_kind = self._get_index_kind(mode)
                if res.source == "lexical":
                    index_kind = IndexKind.LEXICAL
                elif res.source == "vector":
                    index_kind = IndexKind.VECTOR
                elif res.source == "hybrid":
                    index_kind = IndexKind.HYBRID

                segment = RetrievedSegment(
                    segment_id=res.doc_id,
                    score=res.score,
                    content=content,
                    metadata=SegmentMetadata(
                        title=title,
                        url=url,
                        headings=[],  # Solr/Qdrant might not return this structure easily
                        extras={
                            "rank": i + 1,
                            "raw_metadata": json.dumps(meta),
                            "length": db_doc.get("length", 0),
                            "source": res.source,
                        },
                    ),
                    provenance=ProvenanceInfo(
                        index_kind=index_kind,
                        index_snapshot="live",
                        score_components={f"{mode}_score": res.score},
                    ),
                )
                segments.append(segment)

            return QueryResult(
                query_id=query_id,
                segments=segments,
                diagnostics=RetrievalDiagnostics(
                    latency_ms=0,  # TODO: Measure latency
                    config_hash="live_config",
                    index_versions={"solr": "unknown", "qdrant": "unknown"},
                    warnings=[],
                ),
            )

        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return QueryResult(
                query_id=query_id,
                segments=[],
                diagnostics=RetrievalDiagnostics(
                    latency_ms=0,
                    config_hash="error",
                    index_versions={},
                    warnings=[str(e)],
                ),
            )

    async def _get_query_vector(self, text: str, max_retries: int = 3) -> list[float]:
        """
        Generate embedding for query using Ollama (async) with retry logic.

        Args:
            text: Query text to embed
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            4096-dimensional embedding vector
        """
        url = "http://localhost:11434/api/embeddings"
        payload = {"model": "qwen3-embedding:0.6b", "prompt": text}

        last_error = None

        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    embedding = data.get("embedding", [])

                if not embedding:
                    if attempt < max_retries:
                        wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(
                            f"Ollama returned empty embedding (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(
                            "Ollama returned empty embedding after all retries, using mock"
                        )
                        return [0.1] * 4096

                # Dimension check (optional but good for safety)
                # qwen3-embedding:8b produces 4096-dimensional embeddings
                if len(embedding) != 4096:
                    logger.warning(
                        f"Embedding dimension mismatch: got {len(embedding)}, expected 4096. This shouldn't happen with qwen3-embedding:8b."
                    )

                # Success - return the embedding
                if attempt > 0:
                    logger.info(
                        f"Successfully got embedding from Ollama after {attempt + 1} attempts"
                    )
                return embedding

            except httpx.HTTPStatusError as e:
                error_detail = f"HTTP {e.response.status_code}"
                try:
                    error_body = e.response.json()
                    error_detail += f": {error_body}"
                except Exception:
                    error_detail += f": {e.response.text[:200]}"
                last_error = f"HTTP error ({error_detail}): {type(e).__name__}"

                # Retry on 5xx errors, but not on 4xx (client errors)
                if e.response.status_code >= 500 and attempt < max_retries:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Ollama HTTP error (attempt {attempt + 1}/{max_retries + 1}): {last_error}, retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Don't retry on 4xx errors (client errors like 404, 400)
                    logger.error(f"Failed to get embedding from Ollama: {last_error}")
                    break

            except httpx.RequestError as e:
                last_error = f"{type(e).__name__} - {str(e) or 'Connection error'}"

                if attempt < max_retries:
                    wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Failed to connect to Ollama (attempt {attempt + 1}/{max_retries + 1}): {last_error}, retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Failed to connect to Ollama after {max_retries + 1} attempts: {last_error}"
                    )
                    break

            except Exception as e:
                last_error = f"{type(e).__name__} - {str(e) or 'Unknown error'}"

                if attempt < max_retries:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Unexpected error from Ollama (attempt {attempt + 1}/{max_retries + 1}): {last_error}, retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Failed to get embedding from Ollama after {max_retries + 1} attempts: {last_error}"
                    )
                    break

        # All retries exhausted - fallback to mock (but this should be rare)
        logger.error(
            f"All retry attempts exhausted for embedding generation. Using mock embedding. Last error: {last_error}"
        )
        # qwen3-embedding:8b produces 4096-dimensional embeddings
        return [0.1] * 4096

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """
        Retrieve a single document by ID.
        """
        if not self.db:
            logger.warning("Database retriever not initialized")
            return None

        try:
            docs = self.db.get_documents([doc_id])
            return docs.get(doc_id)
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id}: {e}")
            return None

    def _get_index_kind(
        self, mode: Literal["lexical", "vector", "hybrid"]
    ) -> IndexKind:
        """Get the appropriate IndexKind for the retrieval mode."""
        if mode == "lexical":
            return IndexKind.LEXICAL
        elif mode == "vector":
            return IndexKind.VECTOR
        else:  # hybrid
            return IndexKind.HYBRID
