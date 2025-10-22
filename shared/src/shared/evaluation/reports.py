"""
Evaluation reports and experiment manifests.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .metrics import EvaluationDiagnostics, MetricValue
from .runs import RetrievalRun


class EvaluationReport(BaseModel):
    """Evaluation report."""

    model_config = ConfigDict(frozen=True)

    run_metadata: RetrievalRun = Field(..., description="Run metadata")
    metric_values: list[MetricValue] = Field(..., description="Metric values")
    diagnostics: EvaluationDiagnostics = Field(
        ..., description="Evaluation diagnostics"
    )


class ExperimentManifest(BaseModel):
    """Experiment manifest."""

    experiment_id: str = Field(
        ..., 
        description="Experiment identifier",
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    schema_version: str = Field(
        ..., 
        description="Schema version",
        pattern=r"^\d+\.\d+\.\d+$"
    )
    dataset_version: str = Field(
        ..., 
        description="Dataset version",
        pattern=r"^\d+\.\d+\.\d+$"
    )
    config_hash: str = Field(
        ..., 
        description="SHA-256 hash of configuration",
        pattern=r"^[a-fA-F0-9]{64}$"
    )
    run_ids: list[str] = Field(..., description="Run identifiers")
    metrics: list[MetricValue] = Field(..., description="Selected metrics")
    notes: str | None = Field(None, description="Experiment notes")

    @field_validator('run_ids')
    @classmethod
    def validate_run_ids_unique(cls, v):
        """Ensure run_ids are unique."""
        if len(v) != len(set(v)):
            raise ValueError("run_ids must be unique")
        return v
