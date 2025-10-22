"""
Shared types for RAG TREC 2025 project.

This module provides Pydantic models and enums used across the API, CLI, and 
evaluation components. All types are organized by domain (data, retrieval, 
evaluation) with clean import patterns.
"""

# Re-export all models for convenience
from .backend import ApiInfoResponse, HealthResponse, MetadataResponse
from .data import ChunkingSpec, DatasetSpec, IndexTarget
from .enums import IndexKind, MetricName
from .evaluation import (
    EvaluationDiagnostics,
    EvaluationReport,
    ExperimentManifest,
    MetricValue,
    RetrievalRun,
    TrecRunRow,
)
from .retrieval import (
    ProvenanceInfo,
    Query,
    QueryResult,
    RetrievalConfig,
    RetrievalDiagnostics,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedSegment,
    SegmentMetadata,
)

__all__ = [
    # Enums
    "IndexKind",
    "MetricName",
    # Data models
    "DatasetSpec",
    "ChunkingSpec",
    "IndexTarget",
    # Retrieval models
    "RetrievalConfig",
    "Query",
    "RetrievalRequest",
    "RetrievedSegment",
    "SegmentMetadata",
    "ProvenanceInfo",
    "QueryResult",
    "RetrievalResponse",
    "RetrievalDiagnostics",
    # Evaluation models
    "MetricValue",
    "EvaluationDiagnostics",
    "TrecRunRow",
    "RetrievalRun",
    "EvaluationReport",
    "ExperimentManifest",
    # Backend API models
    "MetadataResponse",
    "HealthResponse",
    "ApiInfoResponse",
]
