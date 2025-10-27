"""
Topic models for TREC evaluation.
"""

from pydantic import BaseModel, Field


class Topic(BaseModel):
    """Single TREC topic/query."""

    query_id: str = Field(..., description="Unique query identifier")
    query: str = Field(..., description="Query text")
    narrative: str | None = Field(None, description="Detailed information need")
    question: str | None = Field(None, description="Natural language question")

    @property
    def query_length(self) -> int:
        """Get query length in words."""
        return len(self.query.split())


class TopicSet(BaseModel):
    """Collection of topics with metadata."""

    topics: list[Topic]
    source_file: str
    format: str  # "jsonl" or "trec"

    def __len__(self) -> int:
        """Get number of topics."""
        return len(self.topics)

    def __iter__(self):
        """Iterate over topics."""
        return iter(self.topics)

    def get_by_id(self, query_id: str) -> Topic | None:
        """Get topic by query ID."""
        for topic in self.topics:
            if topic.query_id == query_id:
                return topic
        return None

    @property
    def query_ids(self) -> list[str]:
        """Get all query IDs."""
        return [t.query_id for t in self.topics]
