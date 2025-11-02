"""
TREC run models and validation.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

# Note: TrecRunRow exists in shared/src/shared/evaluation/runs.py
# but uses different field names (topic_id, segment_id vs query_id, doc_id)
# Keeping separate for eval CLI which uses query_id/doc_id convention


class TrecRunRow(BaseModel):
    """Single line in TREC run file."""

    query_id: str
    q0: str = "Q0"  # Literal "Q0" required by TREC format
    doc_id: str
    rank: int = Field(gt=0, description="Rank must be greater than 0")
    score: float = Field(
        allow_inf_nan=False, description="Score must be a finite number"
    )
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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    config_snapshot: dict
    topic_source: str
    retrieval_mode: str
    top_k: int
    num_queries: int


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
        # First group rows by query_id and sort each group by rank
        query_rows = {}
        for row in self.rows:
            if row.query_id not in query_rows:
                query_rows[row.query_id] = []
            query_rows[row.query_id].append(row)

        # Sort each group by rank (ascending) and check monotonicity
        for qid, rows in query_rows.items():
            sorted_rows = sorted(rows, key=lambda r: r.rank)

            # Check for duplicate or missing ranks
            ranks = [r.rank for r in sorted_rows]
            if len(ranks) != len(set(ranks)):
                duplicates = [r for r in ranks if ranks.count(r) > 1]
                errors.append(
                    f"Query {qid} has duplicate ranks: {sorted(set(duplicates))}"
                )

            # Check if ranks are consecutive starting from 1
            expected_ranks = list(range(1, len(sorted_rows) + 1))
            actual_ranks = sorted(ranks)
            if actual_ranks != expected_ranks:
                missing = set(expected_ranks) - set(actual_ranks)
                if missing:
                    errors.append(f"Query {qid} has missing ranks: {sorted(missing)}")

            # Check monotonicity (scores must not increase as rank worsens)
            scores = [r.score for r in sorted_rows]
            for i in range(len(scores) - 1):
                if scores[i] < scores[i + 1]:
                    errors.append(
                        f"Query {qid} has increasing scores: rank {sorted_rows[i].rank} "
                        f"score {scores[i]:.6f} < rank {sorted_rows[i+1].rank} score {scores[i+1]:.6f}"
                    )

        return errors
