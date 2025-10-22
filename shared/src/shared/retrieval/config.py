"""
Retrieval configuration models.
"""

from pydantic import BaseModel, Field, model_validator

from ..data import IndexTarget
from ..enums import IndexKind


class RetrievalConfig(BaseModel):
    """Retrieval configuration."""

    mode: IndexKind = Field(..., description="Retrieval mode")
    index_targets: list[IndexTarget] = Field(
        ..., description="Index targets (must contain at least one entry)", min_length=1
    )
    weights: dict[str, float] | None = Field(
        None,
        description="Weight config (if provided, non-empty, keys match targets)",
    )

    @model_validator(mode="after")
    def validate_config(self):
        """Validate retrieval configuration for completeness and consistency."""
        # Check index_targets is not empty (redundant with min_length but explicit)
        if not self.index_targets:
            raise ValueError("index_targets must contain at least one entry")

        # Check weights if provided
        if self.weights is not None:
            # Check weights is not empty dict
            if not self.weights:
                raise ValueError("weights cannot be an empty dictionary when provided")

            # Check non-negative values
            for key, weight in self.weights.items():
                if weight < 0:
                    raise ValueError(
                        f"Weight for '{key}' must be non-negative, got {weight}"
                    )

            # Check keys match index targets
            target_ids = {target.snapshot_id for target in self.index_targets}
            for key in self.weights:
                if key not in target_ids:
                    raise ValueError(
                        f"Weight key '{key}' not found in index_targets "
                        f"snapshot_ids: {target_ids}"
                    )

            # Check not all zeros
            if sum(self.weights.values()) == 0:
                raise ValueError("Weights cannot all be zero")

        return self
