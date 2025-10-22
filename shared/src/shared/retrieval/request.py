"""
Retrieval request models.
"""

from pydantic import BaseModel, Field, constr

from .config import RetrievalConfig


class Query(BaseModel):
    """Single query specification."""

    query_id: constr(strip_whitespace=True, min_length=1) = Field(
        ..., description="Query identifier"
    )
    query_text: constr(strip_whitespace=True, min_length=1) = Field(
        ..., description="Query text"
    )
    top_k: int = Field(..., gt=0, le=100, description="Number of results to return")


class RetrievalRequest(BaseModel):
    """Retrieval request."""

    schema_version: constr(strip_whitespace=True, min_length=1) = Field(
        ..., description="Schema version"
    )
    dataset_version: constr(strip_whitespace=True, min_length=1) = Field(
        ..., description="Dataset version"
    )
    config_hash: constr(strip_whitespace=True, min_length=1) = Field(
        ..., description="Configuration hash"
    )
    config: RetrievalConfig = Field(..., description="Retrieval configuration")
    queries: list[Query] = Field(..., description="Queries to process", min_items=1)
