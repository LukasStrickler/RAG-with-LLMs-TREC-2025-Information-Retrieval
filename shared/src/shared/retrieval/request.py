"""
Retrieval request models.
"""

from pydantic import BaseModel, Field

from .config import RetrievalConfig


class Query(BaseModel):
    """Single query specification."""

    query_id: str = Field(..., description="Query identifier")
    query_text: str = Field(..., description="Query text")
    top_k: int = Field(..., gt=0, le=100, description="Number of results to return")


class RetrievalRequest(BaseModel):
    """Retrieval request."""

    schema_version: str = Field(..., description="Schema version")
    dataset_version: str = Field(..., description="Dataset version")
    config_hash: str = Field(..., description="Configuration hash")
    config: RetrievalConfig = Field(..., description="Retrieval configuration")
    queries: list[Query] = Field(..., description="Queries to process", min_items=1)
