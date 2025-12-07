"""
Data models for dataset, chunking, and index specifications.

These models are re-exported from database.schema for convenience.
"""

from ..database.schema import ChunkingSpec, Dataset, IndexTarget

# Alias Dataset as DatasetSpec for API compatibility
DatasetSpec = Dataset

__all__ = ["ChunkingSpec", "DatasetSpec", "IndexTarget", "Dataset"]
