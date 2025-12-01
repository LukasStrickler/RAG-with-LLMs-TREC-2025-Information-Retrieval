import errno
import logging
import time
from dataclasses import dataclass
from typing import Any

import psycopg2
import requests
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    doc_id: str
    score: float
    content: str | None = None
    metadata: dict[str, Any] | None = None
    source: str = "unknown"  # "lexical", "vector", or "hybrid"


class SolrRetriever:
    def __init__(self, base_url: str, core: str):
        self.base_url = base_url
        self.core = core
        self.search_url = f"{base_url}/{core}/select"

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        try:
            # Build explicit query for title and body fields
            # Use dismax parser for better relevance
            params = {
                "q": query,
                "defType": "edismax",  # Extended DisMax query parser
                "qf": "title^2 body",  # Query fields: title with boost 2x, body with 1x
                "rows": limit,
                "wt": "json",
                "fl": "id,score,title,url",  # Return these fields (not body, we'll get it from DB)
            }
            response = requests.get(self.search_url, params=params)
            response.raise_for_status()
            data = response.json()

            results = []
            for doc in data.get("response", {}).get("docs", []):
                results.append(
                    SearchResult(
                        doc_id=str(doc["id"]),
                        score=float(doc.get("score", 0.0)),
                        content=None,  # Will be filled from DB
                        metadata={
                            "title": doc.get("title", ""),
                            "url": doc.get("url", ""),
                            "doc_id": str(doc["id"]),
                        },
                        source="lexical",
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Solr search error: {e}")
            return []


class QdrantRetriever:
    def __init__(
        self,
        host: str,
        port: int,
        collection_name: str,
        api_key: str | None = None,
        timeout: int = 60,
    ):
        """
        Initialize Qdrant retriever with timeout and retry configuration.

        Args:
            host: Qdrant host
            port: Qdrant port
            collection_name: Collection name to search
            api_key: Optional API key
            timeout: Request timeout in seconds (default: 60)
        """
        self.client = QdrantClient(
            host=host, port=port, api_key=api_key, https=False, timeout=timeout
        )
        self.collection_name = collection_name
        self.timeout = timeout

    def search(
        self, vector: list[float], limit: int = 10, max_retries: int = 3
    ) -> list[SearchResult]:
        """
        Search Qdrant with retry logic for timeout errors.

        Args:
            vector: Query vector
            limit: Number of results to return
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            List of SearchResult objects
        """
        last_error = None

        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                search_result = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=vector,
                    limit=limit,
                )

                results = []
                for hit in search_result:
                    payload = hit.payload if hit.payload else {}
                    # Extract original doc_id from payload
                    # Qdrant internal ID is a UUID, but we need the MSMARCO ID
                    original_doc_id = (
                        payload.get("doc_id") or payload.get("id") or str(hit.id)
                    )

                    results.append(
                        SearchResult(
                            doc_id=original_doc_id,
                            score=hit.score,
                            content=None,  # Will be filled from DB
                            metadata=payload,
                            source="vector",
                        )
                    )

                # Success - return results
                if attempt > 0:
                    logger.info(f"Qdrant search succeeded after {attempt + 1} attempts")
                return results

            except Exception as e:
                error_str = str(e)
                last_error = error_str
                error_lower = error_str.lower()

                # Check exception type for connection errors
                is_os_error = isinstance(e, OSError)
                errno_value = getattr(e, "errno", None)
                is_connection_errno = errno_value in (
                    errno.ECONNRESET,  # 54 - Connection reset by peer
                    errno.ECONNREFUSED,  # 61 - Connection refused
                    errno.ECONNABORTED,  # 53 - Connection aborted
                    errno.EPIPE,  # 32 - Broken pipe
                    104,  # ECONNRESET on Linux
                )

                # Check if it's a retryable error (timeout, connection, or network errors)
                is_timeout = (
                    "timeout" in error_lower
                    or "timed out" in error_lower
                    or "408" in error_str
                    or "Request Timeout" in error_str
                )

                is_connection_error = (
                    (is_os_error and is_connection_errno)
                    or "connection reset" in error_lower
                    or "connection refused" in error_lower
                    or "connection aborted" in error_lower
                    or "connection closed" in error_lower
                    or "disconnected"
                    in error_lower  # Server disconnected, connection disconnected
                    or "server disconnected"
                    in error_lower  # Server disconnected without sending a response
                    or "[errno 54]"
                    in error_lower  # Connection reset by peer (with brackets)
                    or "errno 54" in error_lower  # Connection reset by peer
                    or "[errno 61]" in error_lower  # Connection refused (with brackets)
                    or "errno 61" in error_lower  # Connection refused
                    or "[errno 104]"
                    in error_lower  # Connection reset by peer Linux (with brackets)
                    or "errno 104" in error_lower  # Connection reset by peer (Linux)
                    or "ssh error" in error_lower
                    or "ssh session not active" in error_lower  # SSH tunnel died
                    or "tunnel" in error_lower
                    or "broken pipe" in error_lower
                    or "network" in error_lower
                    or "connection" in error_lower
                    and (
                        "reset" in error_lower
                        or "refused" in error_lower
                        or "aborted" in error_lower
                        or "closed" in error_lower
                    )
                )

                is_retryable = is_timeout or is_connection_error

                if is_retryable and attempt < max_retries:
                    wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    error_type = "timeout" if is_timeout else "connection"
                    logger.warning(
                        f"Qdrant search {error_type} error (attempt {attempt + 1}/{max_retries + 1}): {error_str[:100]}, "
                        f"retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    # Not retryable, or all retries exhausted
                    if is_retryable:
                        error_type = "timeout" if is_timeout else "connection"
                        logger.error(
                            f"Qdrant search {error_type} error after {max_retries + 1} attempts: {error_str[:200]}"
                        )
                    else:
                        logger.error(
                            f"Qdrant search error (non-retryable): {error_str[:200]}"
                        )
                    break

        # All retries exhausted or non-retryable error
        logger.error(
            f"Qdrant search failed after all retries. Last error: {last_error[:200] if last_error else 'Unknown'}"
        )
        return []


class HybridRetriever:
    def __init__(
        self, solr_retriever: SolrRetriever, qdrant_retriever: QdrantRetriever
    ):
        self.solr = solr_retriever
        self.qdrant = qdrant_retriever

    def search(
        self, query: str, vector: list[float], limit: int = 10, alpha: float = 0.5
    ) -> list[SearchResult]:
        """
        Simple hybrid search combining results.
        Alpha controls the weight: 1.0 = pure vector, 0.0 = pure lexical (if we were doing linear combination).
        Here we'll use Reciprocal Rank Fusion (RRF) as it's robust.
        """
        lexical_results = self.solr.search(query, limit=limit * 2)
        vector_results = self.qdrant.search(vector, limit=limit * 2)

        return self.rrf(lexical_results, vector_results, limit=limit)

    def rrf(
        self,
        list1: list[SearchResult],
        list2: list[SearchResult],
        limit: int = 10,
        k: int = 60,
    ) -> list[SearchResult]:
        """
        Reciprocal Rank Fusion.
        """
        scores = {}

        # Helper to process a list
        def process_list(results):
            for rank, result in enumerate(results):
                if result.doc_id not in scores:
                    scores[result.doc_id] = {
                        "score": 0.0,
                        "doc": result,
                        "sources": set(),
                    }
                scores[result.doc_id]["score"] += 1 / (k + rank + 1)
                scores[result.doc_id]["sources"].add(result.source)

        process_list(list1)
        process_list(list2)

        # Sort by accumulated score
        sorted_docs = sorted(scores.values(), key=lambda x: x["score"], reverse=True)

        final_results = []
        for item in sorted_docs[:limit]:
            # We construct a new SearchResult with the fused score
            original_doc = item["doc"]

            # Determine combined source
            sources = item["sources"]
            if "lexical" in sources and "vector" in sources:
                final_source = "hybrid"
            elif "lexical" in sources:
                final_source = "lexical"
            elif "vector" in sources:
                final_source = "vector"
            else:
                final_source = "unknown"

            final_results.append(
                SearchResult(
                    doc_id=original_doc.doc_id,
                    score=item["score"],
                    content=original_doc.content,
                    metadata=original_doc.metadata,
                    source=final_source,
                )
            )

        return final_results


class DatabaseRetriever:
    """Retrieves full document content from PostgreSQL database."""

    def __init__(self, host: str, port: int, dbname: str, user: str, password: str):
        self.conn_params = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
        }

    def get_documents(self, doc_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Fetch full documents from database by IDs.
        Returns dict mapping doc_id -> {title, body, url, length}
        """
        if not doc_ids:
            return {}

        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()

            # Use parameterized query to prevent SQL injection
            placeholders = ",".join(["%s"] * len(doc_ids))
            query = f"""
                SELECT id, title, body, url, length
                FROM documents
                WHERE id IN ({placeholders})
            """

            cursor.execute(query, doc_ids)
            rows = cursor.fetchall()

            # Build result dict
            result = {}
            for row in rows:
                doc_id, title, body, url, length = row
                result[doc_id] = {
                    "title": title or "",
                    "body": body or "",
                    "url": url or "",
                    "length": length or 0,
                }

            cursor.close()
            conn.close()

            return result

        except Exception as e:
            logger.error(f"Database retrieval error: {e}")
            return {}
