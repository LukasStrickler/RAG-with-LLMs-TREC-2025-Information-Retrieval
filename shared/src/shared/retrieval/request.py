"""
Retrieval request models.
"""

from pydantic import BaseModel, Field, constr


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
    """Simplified retrieval request."""

    mode: constr(strip_whitespace=True, pattern="^(lexical|vector|hybrid)$") = Field(
        default="hybrid", description="Retrieval mode: lexical, vector, or hybrid"
    )
    queries: list[Query] = Field(..., description="Queries to process", min_items=1)
