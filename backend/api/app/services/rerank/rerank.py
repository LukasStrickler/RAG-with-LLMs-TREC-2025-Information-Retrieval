"""
Cross-encoder reranking service using sentence-transformers.
"""

import logging
import time

from sentence_transformers import CrossEncoder
from shared.retrieval.response import QueryResult, RetrievedSegment

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """
    Reranking service using cross-encoder models.

    Uses pre-trained cross-encoder models to rerank retrieved documents
    based on query-document relevance scores.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2",
        device: str | None = None,
    ):
        """
        Initialize the cross-encoder reranker.

        Args:
            model_name: Name of the cross-encoder model to use
            device: Device to run the model on ('cpu', 'cuda', or None for auto)
        """
        self.model_name = model_name
        logger.info("Loading cross-encoder model: %s", model_name)
        self.model = CrossEncoder(model_name, device=device)
        logger.info("Cross-encoder model loaded on device: %s", self.model.device)

    def rerank_query_result(
        self, query_result: QueryResult, query_text: str
    ) -> QueryResult:
        """
        Rerank segments in a QueryResult using cross-encoder scores.

        Args:
            query_result: Original query result with segments
            query_text: Query text for cross-encoder scoring

        Returns:
            New QueryResult with reranked segments and updated scores
        """
        if not query_result.segments:
            logger.warning("No segments to rerank for query: %s", query_result.query_id)
            return query_result

        num_segments = len(query_result.segments)
        # Prepare query-document pairs for cross-encoder
        query_doc_pairs = [
            (query_text, segment.content) for segment in query_result.segments
        ]

        # Get cross-encoder scores with timing
        predict_start = time.time()
        cross_encoder_scores = self.model.predict(query_doc_pairs)
        predict_time = time.time() - predict_start

        logger.info(
            "Reranked query_id=%s: %d segments in %.3fs (%.1fms/segment)",
            query_result.query_id,
            num_segments,
            predict_time,
            (predict_time * 1000) / num_segments if num_segments > 0 else 0,
        )

        # Create new segments with updated scores and provenance
        reranked_segments = []
        for segment, ce_score in zip(
            query_result.segments, cross_encoder_scores, strict=True
        ):
            # Store original score in provenance
            original_score = segment.score
            segment.provenance.score_components["original_score"] = original_score
            segment.provenance.score_components["cross_encoder_score"] = float(ce_score)

            # Update the main score to cross-encoder score
            segment.score = float(ce_score)

            reranked_segments.append(segment)

        # Sort by new cross-encoder scores (descending)
        reranked_segments.sort(key=lambda s: s.score, reverse=True)

        # Update diagnostics to indicate reranking was applied
        query_result.diagnostics.warnings.append(f"Reranked using {self.model_name}")

        # Return new QueryResult with reranked segments
        return QueryResult(
            query_id=query_result.query_id,
            segments=reranked_segments,
            diagnostics=query_result.diagnostics,
        )

    def rerank_segments(
        self, query_text: str, segments: list[RetrievedSegment]
    ) -> list[RetrievedSegment]:
        """
        Rerank a list of segments using cross-encoder scores.

        Args:
            query_text: Query text for cross-encoder scoring
            segments: List of segments to rerank

        Returns:
            Reranked list of segments with updated scores
        """
        if not segments:
            return segments

        # Prepare query-document pairs
        query_doc_pairs = [(query_text, segment.content) for segment in segments]

        # Get cross-encoder scores
        cross_encoder_scores = self.model.predict(query_doc_pairs)

        # Update segments with new scores
        reranked_segments = []
        for segment, ce_score in zip(segments, cross_encoder_scores, strict=True):
            # Store original score in provenance
            segment.provenance.score_components["original_score"] = segment.score
            segment.provenance.score_components["cross_encoder_score"] = float(ce_score)

            # Update the main score
            segment.score = float(ce_score)

            reranked_segments.append(segment)

        # Sort by new scores (descending)
        reranked_segments.sort(key=lambda s: s.score, reverse=True)

        return reranked_segments
