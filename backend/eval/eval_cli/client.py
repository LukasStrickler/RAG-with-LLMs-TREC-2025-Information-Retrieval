"""
API client for calling the retrieval API.
"""

import asyncio

import httpx
from shared.retrieval.request import Query, RetrievalRequest
from shared.retrieval.response import QueryResult, RetrievalResponse

from eval_cli.config import Config
from eval_cli.models.topics import TopicSet


class APIRetrievalClient:
    """Client for calling the retrieval API."""

    def __init__(self, config: Config):
        self.base_url = config.api.base_url
        self.api_key = config.api.api_key or "dev"  # default for dev
        self.timeout = config.api.timeout
        self.max_retries = config.api.max_retries
        self.concurrency = config.api.concurrency

    async def retrieve_batch(
        self,
        topics: TopicSet,
        mode: str = "hybrid",  # lexical, vector, or hybrid
        top_k: int = 100,
    ) -> dict[str, QueryResult]:
        """Retrieve responses for all topics via API."""

        # Convert topics to RetrievalRequest format
        queries = [
            Query(query_id=topic.query_id, query_text=topic.query, top_k=top_k)
            for topic in topics
        ]

        # Create simplified request with mode and queries
        request = RetrievalRequest(mode=mode, queries=queries)

        # Make API call
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/retrieve",
                    json=request.model_dump(),
                    headers={
                        "X-API-Key": self.api_key,
                    },
                )
                response.raise_for_status()
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"❌ Cannot connect to API server at {self.base_url}\n"
                f"   Please ensure the API server is running:\n"
                f"   npm run backend:dev\n"
                f"   Original error: {str(e)}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"❌ API server returned error: {e.response.status_code}\n"
                f"   URL: {e.request.url}\n"
                f"   Response: {e.response.text[:500]}"
            ) from e

        # Parse response
        api_response = RetrievalResponse(**response.json())

        # Convert to dict keyed by query_id - each result maps to its own query_id
        return {result.query_id: result for result in api_response.results}

    def retrieve_batch_sync(
        self,
        topics: TopicSet,
        mode: str = "hybrid",
        top_k: int = 100,
    ) -> dict[str, QueryResult]:
        """Synchronous wrapper for CLI commands."""
        return asyncio.run(self.retrieve_batch(topics, mode, top_k))
