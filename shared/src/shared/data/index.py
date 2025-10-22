"""
Index target specifications.
"""

import re

from pydantic import BaseModel, Field, field_validator

from ..enums import IndexKind


class IndexTarget(BaseModel):
    """Index target specification."""

    kind: IndexKind = Field(..., description="Index type")
    uri: str = Field(..., description="Index URI")
    snapshot_id: str = Field(..., description="Index snapshot identifier")

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v):
        # Accept HTTP URLs or mock:// URIs for testing
        if not (
            v.startswith("http://")
            or v.startswith("https://")
            or v.startswith("mock://")
        ):
            raise ValueError(
                f"uri must be http://, https://, or mock:// protocol, got: {v}"
            )
        return v

    @field_validator("snapshot_id")
    @classmethod
    def validate_snapshot_id(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                f"snapshot_id must contain only alphanumeric, underscore, hyphen: {v}"
            )
        return v
