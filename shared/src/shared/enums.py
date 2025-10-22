"""
Shared enums for the RAG TREC 2025 project.

These enums are used across multiple modules to ensure type safety and consistency.
"""

from enum import Enum


class IndexKind(str, Enum):
    """Types of retrieval indexes supported by the system."""
    
    LEXICAL = "lexical"  # Term-based retrieval (BM25, TF-IDF)
    VECTOR = "vector"  # Dense embedding similarity search
    HYBRID = "hybrid"  # Combined lexical + vector scoring


class MetricName(str, Enum):
    """TREC evaluation metrics."""
    
    NDCG_AT_10 = "ndcg@10"  # Normalized Discounted Cumulative Gain at 10
    MAP_AT_100 = "map@100"  # Mean Average Precision at 100
    MRR_AT_10 = "mrr@10"  # Mean Reciprocal Rank at 10
    RECALL_AT_50 = "recall@50"  # Recall at 50
    RECALL_AT_100 = "recall@100"  # Recall at 100
    HIT_RATE_AT_10 = "hitrate@10"  # Hit Rate at 10
