"""
API client for calling the retrieval API.
"""

import asyncio
from typing import Literal

import httpx
from shared.retrieval.request import Query, RetrievalRequest
from shared.retrieval.response import QueryResult, RetrievalResponse

from eval_cli.config import Config
from eval_cli.models.topics import TopicSet

RetrievalMode = Literal["lexical", "vector", "hybrid"]


class APIRetrievalClient:
    """Client for calling the retrieval API."""

    def __init__(self, config: Config):
        self.base_url = config.api.base_url
        # Get API key value safely, with default for dev
        if config.api.api_key:
            self.api_key = config.api.api_key.get_secret_value()
        else:
            self.api_key = "dev"  # default for dev
        self.timeout = config.api.timeout

    async def retrieve_batch(
        self,
        topics: TopicSet,
        mode: RetrievalMode = "hybrid",
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
        except httpx.TimeoutException as e:
            raise RuntimeError(
                f"❌ API request timed out after {self.timeout} seconds\n"
                f"   Server: {self.base_url}\n"
                f"   Suggestion: Increase timeout in config or check server load\n"
                f"   Original error: {str(e)}"
            ) from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code in (401, 403):
                raise RuntimeError(
                    f"❌ API authentication failed (status {status_code})\n"
                    f"   Please verify your API_KEY in backend/eval/.env\n"
                    f"   Ensure it matches the key configured in the API server\n"
                    f"   Original error: {str(e)}"
                ) from e
            else:
                response_text = (
                    e.response.text[:500] if e.response.text else "(no response body)"
                )
                raise RuntimeError(
                    f"❌ API server returned error: {status_code}\n"
                    f"   URL: {e.request.url}\n"
                    f"   Response: {response_text}\n"
                    f"   Original error: {str(e)}"
                ) from e

        # Parse response
        api_response = RetrievalResponse(**response.json())

        # Convert to dict keyed by query_id - each result maps to its own query_id
        return {result.query_id: result for result in api_response.results}

    def retrieve_batch_sync(
        self,
        topics: TopicSet,
        mode: RetrievalMode = "hybrid",
        top_k: int = 100,
    ) -> dict[str, QueryResult]:
        """Synchronous wrapper for CLI commands."""
        return asyncio.run(self.retrieve_batch(topics, mode, top_k))
