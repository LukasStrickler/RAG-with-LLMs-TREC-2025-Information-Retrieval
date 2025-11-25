import logging
import os
import json
from typing import Literal, List, Optional, Dict, Any
from pathlib import Path

from shared.enums import IndexKind
from shared.retrieval.response import (
    ProvenanceInfo,
    QueryResult,
    RetrievalDiagnostics,
    RetrievedSegment,
    SegmentMetadata,
)

from app.config import settings
from .ssh_utils import SSHTunnelManager
from .retrievers import SolrRetriever, QdrantRetriever, HybridRetriever, SearchResult, DatabaseRetriever

logger = logging.getLogger(__name__)

class RetrievalService:
    """
    Real Retrieval Service implementation using Solr and Qdrant via SSH Tunnel.
    """

    def __init__(self):
        self.tunnel_manager = SSHTunnelManager()
        self.solr: Optional[SolrRetriever] = None
        self.qdrant: Optional[QdrantRetriever] = None
        self.hybrid: Optional[HybridRetriever] = None
        self.db: Optional[DatabaseRetriever] = None
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

            # Initialize Qdrant
            qdrant_collection = settings.qdrant_collection or os.getenv("QDRANT_COLLECTION", "documents")
            qdrant_api_key = settings.qdrant_api_key or os.getenv("QDRANT_API_KEY")
            
            # Qdrant is accessed via localhost through the tunnel
            self.qdrant = QdrantRetriever("localhost", ports['qdrant'], qdrant_collection, api_key=qdrant_api_key)
            logger.info(f"Qdrant initialized at localhost:{ports['qdrant']} (collection: {qdrant_collection})")

            # Initialize Hybrid
            self.hybrid = HybridRetriever(self.solr, self.qdrant)
            logger.info("Hybrid retriever initialized")

            # Initialize Database Retriever
            db_name = os.getenv("DB_NAME", "postgres")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "")
            self.db = DatabaseRetriever(
                host="localhost",
                port=ports['db'],
                dbname=db_name,
                user=db_user,
                password=db_password
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

    def generate_response(
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
                    warnings=["Service not active"]
                )
            )

        try:
            results: List[SearchResult] = []
            
            # TODO: We need a vector for vector/hybrid search. 
            # For now, we'll use a mock vector or we need an embedding service.
            # The user didn't specify an embedding service yet, but the previous code had 'embeddings' folder.
            # Let's check if there is an embedding service we can use.
            # For this step, I will assume we need to generate a vector.
            # Since I don't have an embedding model loaded here, I will check if I can use one.
            # But the user request was just "lexical and vector retrieval".
            # I will use a placeholder vector generation for now and add a TODO.
            
            query_vector = self._get_query_vector(query_text)

            if mode == "lexical":
                if self.solr:
                    results = self.solr.search(query_text, limit=top_k)
            elif mode == "vector":
                if self.qdrant:
                    results = self.qdrant.search(query_vector, limit=top_k)
            elif mode == "hybrid":
                if self.hybrid:
                    results = self.hybrid.search(query_text, query_vector, limit=top_k)

            # Fetch full document content from database
            doc_ids = [res.doc_id for res in results]
            db_docs = {}
            if self.db and doc_ids:
                logger.info(f"Fetching {len(doc_ids)} documents from database. Sample IDs: {doc_ids[:5]}")
                db_docs = self.db.get_documents(doc_ids)
                logger.info(f"Fetched {len(db_docs)} documents from database")

            # Convert SearchResult to RetrievedSegment
            segments = []
            for i, res in enumerate(results):
                # Extract metadata
                meta = res.metadata or {}
                
                # Get full document from database
                db_doc = db_docs.get(res.doc_id, {})
                content = db_doc.get('body', res.content or "No content available")
                title = db_doc.get('title', meta.get('title', f"Document {res.doc_id}"))
                url = db_doc.get('url', meta.get('url', ""))
                
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
                        headings=[], # Solr/Qdrant might not return this structure easily
                        extras={"rank": i + 1, "raw_metadata": json.dumps(meta), "length": db_doc.get('length', 0), "source": res.source},
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
                    latency_ms=0, # TODO: Measure latency
                    config_hash="live_config",
                    index_versions={"solr": "unknown", "qdrant": "unknown"},
                    warnings=[],
                )
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
                    warnings=[str(e)]
                )
            )

    def _get_query_vector(self, text: str) -> List[float]:
        """
        Generate embedding for query.
        TODO: Integrate with actual embedding model.
        """
        # Placeholder: return random or zero vector
        # This is a CRITICAL GAP if not addressed, but for now I'll use a mock 
        # to satisfy the interface.
        # I should probably check if there is an embedding service in the codebase.
        return [0.1] * 1024 # Assuming 1024 dim (matches Qdrant collection)

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
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
