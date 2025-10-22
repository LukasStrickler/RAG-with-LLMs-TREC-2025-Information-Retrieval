"""
Dataset and index configuration endpoints.

Provides endpoints for retrieving metadata about datasets, chunking specifications,
and available indexes for the retrieval system.
"""

from .router import router

__all__ = ["router"]
