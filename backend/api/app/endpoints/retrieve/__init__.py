"""
Document retrieval endpoints.

Provides endpoints for single and batch document retrieval operations,
supporting both lexical and semantic retrieval modes with hybrid fusion.
"""

from .router import router

__all__ = ["router"]
