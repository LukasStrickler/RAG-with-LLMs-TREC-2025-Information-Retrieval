"""
Baseline loader for organizer baseline runs.
"""

from eval_cli.io.runs import read_trec_run
from eval_cli.models.runs import TrecRun


class BaselineLoader:
    """Load organizer baseline runs for comparison."""

    def __init__(self, config):
        self.config = config

    def load_baseline(self, year: str) -> TrecRun:
        """Load organizer baseline run."""
        baseline_path = self.config.get_data_path(self.config.paths.baselines[year])

        if not baseline_path.exists():
            raise FileNotFoundError(f"Baseline file not found: {baseline_path}")

        # Generate run_id from filename
        run_id = baseline_path.stem

        return read_trec_run(baseline_path, run_id)

    def get_baseline_stats(self, year: str) -> dict[str, float]:
        """Get baseline performance statistics."""
        baseline = self.load_baseline(year)

        # Count queries and documents
        query_counts = {}
        for row in baseline.rows:
            query_counts[row.query_id] = query_counts.get(row.query_id, 0) + 1

        return {
            "num_queries": len(query_counts),
            "avg_docs_per_query": sum(query_counts.values()) / len(query_counts),
            "total_docs": len(baseline.rows),
        }
