"""
Baseline comparison models.
"""

from pydantic import BaseModel


class BaselineRun(BaseModel):
    """Organizer baseline run."""

    year: str
    name: str
    metrics: dict[str, float]
    description: str | None = None


class BaselineComparison(BaseModel):
    """Comparison against baselines."""

    run_metrics: dict[str, float]
    baselines: list[BaselineRun]
    comparisons: dict[str, dict[str, float]]  # {baseline_name: {metric: delta}}
