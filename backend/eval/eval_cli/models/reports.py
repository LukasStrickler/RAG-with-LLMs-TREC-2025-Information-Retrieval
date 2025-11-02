"""
Evaluation report models.
"""

from typing import Literal, get_args

from pydantic import BaseModel, model_validator

MetricStatus = Literal["pass", "warn", "fail", "unknown"]
OverallStatus = Literal["pass", "warn", "fail", "unknown"]


class MetricValue(BaseModel):
    """Single metric value with target comparison."""

    name: str
    value: float
    target: float | None = None
    status: MetricStatus
    higher_is_better: bool = True


class EvaluationReport(BaseModel):
    """Complete evaluation report."""

    metrics: list[MetricValue]
    status_counts: dict[str, int]
    overall_status: OverallStatus

    @model_validator(mode="after")
    def validate_status_counts(self) -> "EvaluationReport":
        """Ensure status_counts matches actual metric statuses and overall_status is valid."""
        # Get valid status values dynamically from MetricStatus type
        valid_statuses = get_args(MetricStatus)

        # Recompute counts from metrics
        computed_counts: dict[str, int] = {status: 0 for status in valid_statuses}
        for metric in self.metrics:
            if metric.status in computed_counts:
                computed_counts[metric.status] += 1

        # Validate provided counts match computed
        for status in valid_statuses:
            if self.status_counts.get(status, 0) != computed_counts[status]:
                raise ValueError(
                    f"status_counts mismatch for '{status}': "
                    f"expected {computed_counts[status]}, got {self.status_counts.get(status, 0)}"
                )

        # overall_status is validated by Pydantic via the OverallStatus Literal type

        return self
