"""
Topic models for TREC evaluation.
"""

import re
from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr, model_validator


class Topic(BaseModel):
    """Single TREC topic/query."""

    query_id: str = Field(..., description="Unique query identifier")
    query: str = Field(..., description="Query text")
    narrative: str | None = Field(None, description="Detailed information need")
    question: str | None = Field(None, description="Natural language question")

    @property
    def query_length(self) -> int:
        """Get query length in words using whitespace-aware tokenization."""
        # Use regex to count non-whitespace tokens (handles multiple spaces/tabs)
        tokens = re.findall(r"\S+", self.query)
        return len(tokens)


class TopicSet(BaseModel):
    """Collection of topics with metadata."""

    topics: list[Topic]
    source_file: str
    format: Literal["jsonl", "trec", "simple"] = Field(description="Topic file format")

    _topic_lookup: dict[str, Topic] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def build_lookup(self) -> "TopicSet":
        """Build O(1) lookup dict after validation."""
        self._topic_lookup = {topic.query_id: topic for topic in self.topics}
        return self

    def __len__(self) -> int:
        """Get number of topics."""
        return len(self.topics)

    def __iter__(self) -> Iterator[Topic]:
        """Iterate over topics."""
        return iter(self.topics)

    def get_by_id(self, query_id: str) -> Topic | None:
        """Get topic by query ID (O(1) lookup)."""
        return self._topic_lookup.get(query_id)

    @property
    def query_ids(self) -> list[str]:
        """Get all query IDs."""
        return [t.query_id for t in self.topics]
