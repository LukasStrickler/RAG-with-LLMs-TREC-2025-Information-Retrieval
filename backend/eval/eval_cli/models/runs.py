"""
TREC run models and validation.
"""

from datetime import datetime

from pydantic import BaseModel, Field

# Note: TrecRunRow exists in shared/src/shared/evaluation/runs.py
# but uses different field names (topic_id, segment_id vs query_id, doc_id)
# Keeping separate for eval CLI which uses query_id/doc_id convention


class TrecRunRow(BaseModel):
    """Single line in TREC run file."""

    query_id: str
    q0: str = "Q0"  # Literal "Q0" required by TREC format
    doc_id: str
    rank: int
    score: float
    run_id: str

    def to_trec_line(self) -> str:
        """Format as TREC 6-column TSV."""
        return (
            f"{self.query_id}\t{self.q0}\t{self.doc_id}\t{self.rank}\t"
            f"{self.score:.6f}\t{self.run_id}"
        )


class RunMetadata(BaseModel):
    """Metadata for reproducibility."""

    run_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    config_snapshot: dict
    topic_source: str
    retrieval_mode: str
    top_k: int
    num_queries: int
    performance_level: str | None = None


class TrecRun(BaseModel):
    """Complete TREC run with metadata."""

    rows: list[TrecRunRow]
    metadata: RunMetadata

    def validate_format(self) -> list[str]:
        """Validate TREC format constraints."""
        errors = []

        # Check max 100 docs per query
        query_counts = {}
        for row in self.rows:
            query_counts[row.query_id] = query_counts.get(row.query_id, 0) + 1

        for qid, count in query_counts.items():
            if count > 100:
                errors.append(f"Query {qid} has {count} results (max 100)")

        # Check unique ranks per query
        query_ranks = {}
        for row in self.rows:
            if row.query_id not in query_ranks:
                query_ranks[row.query_id] = set()
            if row.rank in query_ranks[row.query_id]:
                errors.append(f"Query {row.query_id} has duplicate rank {row.rank}")
            query_ranks[row.query_id].add(row.rank)

        # Check non-increasing scores per query
        query_scores = {}
        for row in self.rows:
            if row.query_id not in query_scores:
                query_scores[row.query_id] = []
            query_scores[row.query_id].append(row.score)

        for qid, scores in query_scores.items():
            for i in range(len(scores) - 1):
                if scores[i] < scores[i + 1]:
                    errors.append(
                        f"Query {qid} has increasing scores at ranks {i+1}, {i+2}"
                    )

        return errors
