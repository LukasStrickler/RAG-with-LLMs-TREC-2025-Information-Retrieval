"""
API client for calling the retrieval API.
"""

import asyncio
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError
from shared.backend.responses import MetadataResponse
from shared.retrieval.request import Query, RetrievalRequest
from shared.retrieval.response import QueryResult, RetrievalResponse

from eval_cli.config import Config
from eval_cli.models.topics import TopicSet

logger = logging.getLogger(__name__)
RetrievalMode = Literal["lexical", "vector", "hybrid"]


class RetrievalBatchResponse(BaseModel):
    """Response from batch retrieval including results and API metadata."""

    results: dict[str, QueryResult]
    dataset_version: str
    config_hash: str
    schema_version: str
    request_id: str


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

        logger.info(
            f"APIRetrievalClient initialized: base_url={self.base_url}, "
            f"api_key={'***' + self.api_key[-4:] if len(self.api_key) > 4 else '***'}, "
            f"timeout={self.timeout}s"
        )

    async def retrieve_batch(
        self,
        topics: TopicSet,
        mode: RetrievalMode = "hybrid",
        top_k: int = 100,
        rerank: bool = False,
    ) -> RetrievalBatchResponse:
        """Retrieve responses for all topics via API.

        Returns both the query results and API response metadata (dataset_version,
        config_hash, schema_version, request_id) for reproducibility.
        """

        # Convert topics to RetrievalRequest format
        queries = [
            Query(query_id=topic.query_id, query_text=topic.query, top_k=top_k)
            for topic in topics
        ]

        # Create simplified request with mode and queries
        request = RetrievalRequest(mode=mode, queries=queries, rerank=rerank)

        url = f"{self.base_url}/api/v1/retrieve"
        logger.info(
            f"Making API request to {url} with {len(queries)} queries, "
            f"mode={mode}, timeout={self.timeout}s"
        )
        logger.debug(f"Client: Making API request to {url} with {len(queries)} queries")

        # Make API call
        try:
            # Use Timeout object for better control - set read timeout to config value
            # Connect timeout is shorter (30s), read timeout is longer for large requests
            timeout = httpx.Timeout(
                connect=30.0,  # Connection timeout: 30 seconds
                read=self.timeout,  # Read timeout: from config (for long-running reranking)
                write=30.0,  # Write timeout: 30 seconds
                pool=30.0,  # Pool timeout: 30 seconds
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json=request.model_dump(),
                    headers={
                        "X-API-Key": self.api_key,
                    },
                )
                logger.info(f"API response status: {response.status_code}")
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
        try:
            response_json = response.json()
        except Exception as json_error:
            request_url = getattr(response, "url", None) or (
                response.request.url if hasattr(response, "request") else "unknown"
            )
            raise RuntimeError(
                f"❌ Failed to parse API response as JSON\n"
                f"   URL: {request_url}\n"
                f"   Status: {response.status_code}\n"
                f"   Response text (first 500 chars): {response.text[:500]}\n"
                f"   JSON parse error: {json_error}"
            ) from json_error

        try:
            api_response = RetrievalResponse(**response_json)
        except ValidationError as validation_error:
            request_url = getattr(response, "url", None) or (
                response.request.url if hasattr(response, "request") else "unknown"
            )
            raise RuntimeError(
                f"❌ API response validation failed\n"
                f"   URL: {request_url}\n"
                f"   Status: {response.status_code}\n"
                f"   Validation errors: {validation_error}\n"
                f"   Response JSON (first 500 chars): {str(response_json)[:500]}"
            ) from validation_error

        # Convert to dict keyed by query_id - each result maps to its own query_id
        results_dict = {result.query_id: result for result in api_response.results}

        # Return both results and metadata
        return RetrievalBatchResponse(
            results=results_dict,
            dataset_version=api_response.dataset_version,
            config_hash=api_response.config_hash,
            schema_version=api_response.schema_version,
            request_id=api_response.request_id,
        )

    def retrieve_batch_sync(
        self,
        topics: TopicSet,
        mode: RetrievalMode = "hybrid",
        top_k: int = 100,
        rerank: bool = False,
    ) -> RetrievalBatchResponse:
        """Synchronous wrapper for CLI commands."""
        return asyncio.run(self.retrieve_batch(topics, mode, top_k, rerank))

    async def get_metadata(self) -> MetadataResponse | None:
        """Get metadata from the API metadata endpoint.

        Returns None if the endpoint is unavailable or returns an error.
        This is a non-blocking call that gracefully handles failures.
        """
        url = f"{self.base_url}/api/v1/metadata"
        logger.info(f"Fetching metadata from {url}")

        try:
            timeout = httpx.Timeout(
                connect=10.0,  # Connection timeout: 10 seconds
                read=10.0,  # Read timeout: 10 seconds
                write=10.0,  # Write timeout: 10 seconds
                pool=10.0,  # Pool timeout: 10 seconds
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers={
                        "X-API-Key": self.api_key,
                    },
                )
                response.raise_for_status()
                response_json = response.json()
                return MetadataResponse(**response_json)
        except httpx.ConnectError:
            logger.warning(
                f"Could not connect to metadata endpoint at {url}. "
                "Metadata will not be included in run files."
            )
            return None
        except httpx.TimeoutException:
            logger.warning(
                f"Metadata endpoint at {url} timed out. "
                "Metadata will not be included in run files."
            )
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Metadata endpoint returned error {e.response.status_code}. "
                "Metadata will not be included in run files."
            )
            return None
        except (ValidationError, Exception) as e:
            logger.warning(
                f"Failed to parse metadata response: {e}. "
                "Metadata will not be included in run files."
            )
            return None

    def get_metadata_sync(self) -> MetadataResponse | None:
        """Synchronous wrapper for get_metadata."""
        return asyncio.run(self.get_metadata())
