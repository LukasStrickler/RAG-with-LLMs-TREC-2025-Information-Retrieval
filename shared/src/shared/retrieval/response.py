"""
Retrieval response models.
"""

from pydantic import BaseModel, Field

from ..enums import IndexKind


class SegmentMetadata(BaseModel):
    """Segment metadata."""

    title: str | None = Field(None, description="Segment title")
    url: str | None = Field(None, description="Segment URL")
    headings: list[str] = Field(default_factory=list, description="Section headings")
    extras: dict[str, str | int | float | bool] = Field(
        default_factory=dict, description="Additional metadata"
    )


class ProvenanceInfo(BaseModel):
    """Provenance information for retrieved segments."""

    index_kind: IndexKind = Field(..., description="Index type")
    index_snapshot: str = Field(..., description="Index snapshot ID")
    score_components: dict[str, float] = Field(
        default_factory=dict, description="Score components"
    )


class RetrievedSegment(BaseModel):
    """Retrieved segment."""

    segment_id: str = Field(..., description="Segment identifier")
    score: float = Field(..., description="Retrieval score")
    metadata: SegmentMetadata = Field(..., description="Segment metadata")
    provenance: ProvenanceInfo = Field(..., description="Provenance information")


class RetrievalDiagnostics(BaseModel):
    """Retrieval diagnostics."""

    latency_ms: float = Field(..., description="Retrieval latency in milliseconds")
    config_hash: str = Field(..., description="Configuration hash")
    index_versions: dict[str, str] = Field(
        default_factory=dict, description="Index versions"
    )
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


class QueryResult(BaseModel):
    """Result for a single query."""

    query_id: str = Field(..., description="Query identifier")
    segments: list[RetrievedSegment] = Field(..., description="Retrieved segments")
    diagnostics: RetrievalDiagnostics = Field(..., description="Retrieval diagnostics")


class RetrievalResponse(BaseModel):
    """Retrieval response."""

    schema_version: str = Field(..., description="Schema version")
    dataset_version: str = Field(..., description="Dataset version")
    config_hash: str = Field(..., description="Configuration hash")
    request_id: str = Field(..., description="Request identifier")
    results: list[QueryResult] = Field(..., description="Query results", min_items=1)
