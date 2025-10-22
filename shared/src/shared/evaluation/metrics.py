"""
Evaluation metrics and diagnostics.
"""

from pydantic import BaseModel, Field

from ..enums import MetricName


class MetricValue(BaseModel):
    """
    Metric value with metadata for TREC-style evaluation workflows.

    This model represents a single evaluation metric result with associated metadata
    for reproducibility and analysis. It's designed for use in evaluation pipelines,
    benchmarking, and research auditing.

    Examples:
        MetricValue(
            name=MetricName.NDCG_AT_10,
            value=0.65,
            higher_is_better=True,
            target=0.60,
            pass_flag=True
        )
        MetricValue(
            name=MetricName.MAP_AT_100,
            value=0.28,
            higher_is_better=True,
            target=None,
            pass_flag=None
        )

    The model supports both per-query and per-system metrics, with the pass_flag
    indicating whether a target threshold was met (useful for automated evaluation
    pipelines and CI/CD integration).
    """

    name: MetricName = Field(..., description="Metric name")
    value: float = Field(..., description="Metric value")
    higher_is_better: bool = Field(..., description="Whether higher values are better")
    target: float | None = Field(None, description="Target value")
    pass_flag: bool | None = Field(None, description="Whether target was met")


class EvaluationDiagnostics(BaseModel):
    """Evaluation diagnostics."""

    trec_eval_version: str = Field(..., description="trec_eval version")
    runtime_seconds: float = Field(..., description="Evaluation runtime in seconds")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
