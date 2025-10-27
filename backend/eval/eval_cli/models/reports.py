"""
Evaluation report models.
"""

from pydantic import BaseModel


class MetricValue(BaseModel):
    """Single metric value with target comparison."""

    name: str
    value: float
    target: float | None = None
    status: str  # "pass", "warn", "fail", "unknown"
    higher_is_better: bool = True


class EvaluationReport(BaseModel):
    """Complete evaluation report."""

    metrics: list[MetricValue]
    status_counts: dict[str, int]
    overall_status: str  # "pass", "warn", "fail", "unknown"
