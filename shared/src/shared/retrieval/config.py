"""
Retrieval configuration models.
"""

from pydantic import BaseModel, Field, model_validator

from ..data import IndexTarget
from ..enums import IndexKind


class RetrievalConfig(BaseModel):
    """Retrieval configuration."""

    mode: IndexKind = Field(..., description="Retrieval mode")
    index_targets: list[IndexTarget] = Field(..., description="Index targets")
    weights: dict[str, float] | None = Field(None, description="Weight configuration")

    @model_validator(mode="after")
    def validate_weights(self):
        if self.weights:
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
