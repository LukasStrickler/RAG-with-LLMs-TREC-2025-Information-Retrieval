"""
Baseline loader for organizer baseline runs.
"""

from collections import Counter

from eval_cli.config import Config
from eval_cli.io.runs import read_trec_run
from eval_cli.models.runs import TrecRun


class BaselineLoader:
    """Load organizer baseline runs for comparison."""

    def __init__(self, config: Config):
        self.config = config

    def load_baseline(self, year: str) -> TrecRun:
        """Load organizer baseline run."""
        if year not in self.config.paths.baselines:
            available_years = list(self.config.paths.baselines.keys())
            raise KeyError(
                f"Unknown baseline year '{year}'. Available years: {available_years}"
            )
        baseline_path = self.config.get_data_path(self.config.paths.baselines[year])

        if not baseline_path.exists():
            raise FileNotFoundError(f"Baseline file not found: {baseline_path}")

        # Generate run_id from filename
        run_id = baseline_path.stem

        return read_trec_run(baseline_path, run_id)

    def get_baseline_stats(self, year: str) -> dict[str, int | float]:
        """Get baseline performance statistics."""
        try:
        baseline = self.load_baseline(year)
        except KeyError:
            raise

        # Count queries and documents using Counter
        query_counts = Counter(row.query_id for row in baseline.rows)

        if len(query_counts) == 0:
            return {
                "num_queries": 0.0,
                "avg_docs_per_query": 0.0,
                "total_docs": 0.0,
            }

        return {
            "num_queries": float(len(query_counts)),
            "avg_docs_per_query": float(sum(query_counts.values()) / len(query_counts)),
            "total_docs": float(len(baseline.rows)),
        }
