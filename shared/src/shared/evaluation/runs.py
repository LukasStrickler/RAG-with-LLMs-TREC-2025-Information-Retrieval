"""
TREC run format and retrieval run models.
"""

from pydantic import BaseModel, Field, model_validator

from ..retrieval import RetrievalRequest, RetrievalResponse


class TrecRunRow(BaseModel):
    """TREC run format row."""

    topic_id: str = Field(..., description="Topic/query ID")
    q0: str = Field(default="Q0", description="TREC format field")
    segment_id: str = Field(..., description="Segment ID")
    rank: int = Field(..., description="Rank (1-100)", ge=1, le=100)
    score: float = Field(..., description="Score")
    run_id: str = Field(..., description="Run ID")

    # Score validation is handled at the run level for monotonicity


class TrecRun(BaseModel):
    """Full TREC run with validation."""

    rows: list[TrecRunRow]

    @model_validator(mode="after")
    def validate_monotonicity(self):
        """Ensure scores are non-increasing within each topic."""
        from collections import defaultdict

        topics = defaultdict(list)
        for row in self.rows:
            topics[row.topic_id].append(row)

        for topic_id, rows in topics.items():
            sorted_rows = sorted(rows, key=lambda r: r.rank)
            for i in range(1, len(sorted_rows)):
                if sorted_rows[i].score > sorted_rows[i - 1].score:
                    raise ValueError(
                        f"Score monotonicity violation in topic {topic_id}: "
                        f"rank {sorted_rows[i].rank} score {sorted_rows[i].score} > "
                        f"rank {sorted_rows[i-1].rank} score {sorted_rows[i-1].score}"
                    )
        return self


class RetrievalRun(BaseModel):
    """Retrieval run metadata."""

    run_id: str = Field(..., description="Run identifier")
    schema_version: str = Field(..., description="Schema version")
    dataset_version: str = Field(..., description="Dataset version")
    config_hash: str = Field(..., description="Configuration hash")
    request: RetrievalRequest = Field(..., description="Original request")
    response: RetrievalResponse = Field(..., description="Response")
