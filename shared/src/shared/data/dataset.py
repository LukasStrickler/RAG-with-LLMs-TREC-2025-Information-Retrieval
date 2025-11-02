"""
Dataset and chunking specifications.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class DatasetSpec(BaseModel):
    """Dataset metadata specification."""

    name: str = Field(..., description="Dataset name")
    version: str = Field(..., description="Dataset version")
    split: str | None = Field(None, description="Dataset split (train/dev/test)")
    release_date: date = Field(
        ...,
        description="Dataset release date",
    )
    source_uri: HttpUrl = Field(..., description="Source URI for dataset")


class ChunkingSpec(BaseModel):
    """Text chunking configuration."""

    chunk_size: int = Field(..., gt=0, description="Chunk size in tokens")
    overlap: int = Field(..., ge=0, description="Overlap between chunks in tokens")
    tokenizer: str = Field(..., description="Tokenizer name")
    strategy: Literal["fixed", "semantic", "sliding"] = Field(
        ..., description="Chunking strategy"
    )

    @model_validator(mode="after")
    def validate_overlap(self):
        if self.overlap >= self.chunk_size:
            raise ValueError(
                f"overlap ({self.overlap}) must be < chunk_size ({self.chunk_size})"
            )
        return self
