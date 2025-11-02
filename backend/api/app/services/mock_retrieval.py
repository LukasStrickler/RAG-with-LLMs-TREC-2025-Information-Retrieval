"""
MOCK Retrieval Service - FOR DEVELOPMENT/TESTING ONLY

TODO: Replace this entire file with real retrieval implementation:
1. Create a RetrievalService class that connects to:
   - BM25 index for lexical retrieval
   - Vector database for semantic retrieval
   - Hybrid fusion engine
2. Implement actual document retrieval with real scores
3. Remove all mock data generation logic
4. Delete this file once real implementation is complete

This mock service generates realistic responses for testing the evaluation pipeline.
"""

import logging
import random
from pathlib import Path
from typing import Literal

import numpy as np
from shared.enums import IndexKind
from shared.retrieval.response import (
    ProvenanceInfo,
    QueryResult,
    RetrievalDiagnostics,
    RetrievedSegment,
    SegmentMetadata,
)

logger = logging.getLogger(__name__)


class MockRetrievalService:
    """
    MOCK Retrieval Service - FOR DEVELOPMENT/TESTING ONLY

    TODO: Replace this entire class with real retrieval implementation.
    This class generates mock responses for testing the evaluation pipeline.
    """

    def __init__(self, qrels_path: Path, seed: int = 42):
        """
        Initialize with qrels for realistic document IDs.

        Args:
            qrels_path: Path to qrels file containing relevance judgments
            seed: Random seed for reproducibility (default: 42)
        """
        self.qrels = self._load_qrels(qrels_path)
        self.candidate_docs = self._prepare_candidate_docs()

        # Score generation parameters
        self.score_range = [0.0, 1.0]
        self.relevance_bias = 0.3
        self.position_decay = 0.1

        # Use instance-level RNGs for reproducibility and test isolation
        self._rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)

    def _load_qrels(self, qrels_path: Path) -> dict[str, set[str]]:
        """Load qrels and return dict of query_id -> set of relevant doc IDs."""
        qrels = {}

        if not qrels_path.exists():
            logger.warning(f"Qrels file not found: {qrels_path}")
            return qrels

        with open(qrels_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3:
                    query_id = parts[0]
                    doc_id = parts[2]
                    relevance = int(parts[3]) if len(parts) > 3 else 1

                    if relevance > 0:  # Only relevant documents
                        if query_id not in qrels:
                            qrels[query_id] = set()
                        qrels[query_id].add(doc_id)

        return qrels

    def _prepare_candidate_docs(self) -> dict[str, dict[str, list[str]]]:
        """Pre-compute per-query relevant/irrelevant pools using qrels."""
        candidates = {}

        for query_id, relevant_docs in self.qrels.items():
            relevant = sorted(list(relevant_docs))
            # Generate synthetic irrelevant docs
            irrelevant = [f"spoof_{query_id}_{i:04d}" for i in range(1000)]
            candidates[query_id] = {"relevant": relevant, "irrelevant": irrelevant}

        return candidates

    def generate_response(
        self,
        query_id: str,
        query_text: str,
        top_k: int = 100,
        mode: Literal["lexical", "vector", "hybrid"] = "hybrid",
    ) -> QueryResult:
        """Generate mock retrieval response for a single query."""

        # Sample document IDs (prefer judged docs from qrels)
        retrieved_docs = self._sample_doc_ids(query_id, top_k)

        # Generate scores based on mode
        # Different modes have different performance characteristics
        scores = self._generate_scores_by_mode(len(retrieved_docs), mode)

        # Create RetrievedSegment objects
        segments = []
        for i, (doc_id, score) in enumerate(zip(retrieved_docs, scores, strict=False)):
            segment = RetrievedSegment(
                segment_id=doc_id,
                score=score,
                content=(
                    f"Mock content for document {doc_id}. "
                    f"This is a placeholder for the actual retrieved "
                    f"segment text content."
                ),
                metadata=SegmentMetadata(
                    title=f"Mock Document {doc_id}",
                    url=f"https://example.com/doc/{doc_id}",
                    headings=[f"Section {i+1}"],
                    extras={"rank": i + 1},
                ),
                provenance=ProvenanceInfo(
                    index_kind=self._get_index_kind(mode),
                    index_snapshot=f"mock_{mode}_snapshot_001",
                    score_components={f"{mode}_score": score},
                ),
            )
            segments.append(segment)

        # Create diagnostics
        diagnostics = RetrievalDiagnostics(
            latency_ms=self._rng.randint(50, 200),
            config_hash="mock_config_hash",
            index_versions={"mock_index": "v1.0"},
            warnings=[],
        )

        return QueryResult(
            query_id=query_id, segments=segments, diagnostics=diagnostics
        )

    def _sample_doc_ids(self, query_id: str, top_k: int) -> list[str]:
        """Prefer judged docs so trec_eval output is meaningful."""
        if query_id in self.candidate_docs:
            relevant = self.candidate_docs[query_id]["relevant"]
            irrelevant = self.candidate_docs[query_id]["irrelevant"]
            sample = []

            # Ensure at least one relevant doc when available
            if relevant:
                sample.extend(
                    self._rng.sample(relevant, min(len(relevant), max(1, top_k // 3)))
                )

            # Fill remaining ranks with irrelevance pool
            remaining = top_k - len(sample)
            if remaining > 0:
                sample.extend(
                    self._rng.sample(irrelevant, min(remaining, len(irrelevant)))
                )

            return sample[:top_k]

        # Fallback: generate synthetic IDs when no qrels available
        return [f"segment_{i:06d}" for i in range(1, top_k + 1)]

    def _generate_scores(self, num_docs: int) -> list[float]:
        """Generate realistic retrieval scores."""
        # Base score range
        min_score, max_score = self.score_range

        # Generate scores with exponential decay (realistic ranking)
        scores = []
        for i in range(num_docs):
            # Exponential decay with some randomness
            decay_factor = np.exp(-i * self.position_decay)
            base_score = max_score * decay_factor

            # Add noise
            noise = self._np_rng.normal(0, 0.05)
            score = base_score + noise

            # Bias top-ranked items toward higher scores
            # to simulate better performance tiers
            if i < 10:
                score += self.relevance_bias

            score = max(min_score, min(max_score, score))

            scores.append(score)

        # Sort in descending order
        scores.sort(reverse=True)

        return scores

    def _generate_scores_by_mode(
        self, num_docs: int, mode: Literal["lexical", "vector", "hybrid"]
    ) -> list[float]:
        """Generate scores based on retrieval mode."""
        # All modes use the same score generation for mock data
        return self._generate_scores(num_docs)

    def _get_index_kind(
        self, mode: Literal["lexical", "vector", "hybrid"]
    ) -> IndexKind:
        """Get the appropriate IndexKind for the retrieval mode."""
        if mode == "lexical":
            return IndexKind.LEXICAL
        elif mode == "vector":
            return IndexKind.VECTOR
        else:  # hybrid
            return IndexKind.HYBRID
