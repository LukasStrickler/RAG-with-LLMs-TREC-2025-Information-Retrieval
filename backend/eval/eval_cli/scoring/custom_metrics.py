"""
Custom metrics for evaluation.
"""

from collections import defaultdict

from eval_cli.io.qrels import Qrels
from eval_cli.models.runs import TrecRun


def _group_by_query(trec_run: TrecRun) -> dict[str, list]:
    """Group TREC run rows by query_id."""
    query_results = defaultdict(list)
    for row in trec_run.rows:
        query_results[row.query_id].append(row)
    return dict(query_results)


def compute_hitrate_10(trec_run: TrecRun, qrels: Qrels) -> float:
    """
    Compute HitRate@10 (binary success in top 10).

    HitRate@10 measures the proportion of queries for which at least one
    relevant document appears in the top 10 retrieved results.

    Standard practice: Only queries with at least one relevant document
    in qrels are included in the calculation (matching trec_eval behavior).

    Returns:
        HitRate@10 score between 0.0 and 1.0, or 0.0 if no valid queries.
    """
    if not trec_run.rows:
        return 0.0

    successful_queries = 0
    total_queries_with_relevant = 0

    # Group run rows by query
    query_results = _group_by_query(trec_run)

    for query_id, results in query_results.items():
        # Get relevant documents for this query
        relevant_docs = qrels.get_relevant_docs(query_id)

        # Only evaluate queries that have at least one relevant document
        # (standard IR evaluation practice, matching trec_eval behavior)
        if not relevant_docs:
            continue

        total_queries_with_relevant += 1

        # Get top 10 results (sorted by rank, ascending)
        # Note: The rank field is authoritative - rank 1-10 are the top 10, regardless of scores.
        # Ranks are assigned deterministically in build_trec_run() with tie-breaking by doc_id
        # when scores are equal, ensuring reproducible evaluation results.
        top_10_docs = {row.doc_id for row in sorted(results, key=lambda x: x.rank)[:10]}

        # Check if any relevant doc is in top 10
        if top_10_docs & relevant_docs:
            successful_queries += 1

    return (
        successful_queries / total_queries_with_relevant
        if total_queries_with_relevant > 0
        else 0.0
    )


def compute_coverage_stats(trec_run: TrecRun, qrels: Qrels) -> dict[str, int]:
    """Compute coverage statistics."""
    if not trec_run.rows:
        return {
            "queries_with_judgements": 0,
            "queries_without_judgements": 0,
            "total_relevant_docs": 0,
            "retrieved_relevant_docs": 0,
        }

    stats = {
        "queries_with_judgements": 0,
        "queries_without_judgements": 0,
        "total_relevant_docs": 0,
        "retrieved_relevant_docs": 0,
    }

    # Group run rows by query
    query_results = _group_by_query(trec_run)

    for query_id, results in query_results.items():
        relevant_docs = qrels.get_relevant_docs(query_id)

        if relevant_docs:
            stats["queries_with_judgements"] += 1
            stats["total_relevant_docs"] += len(relevant_docs)

            # Count retrieved relevant docs
            retrieved_docs = {row.doc_id for row in results}
            stats["retrieved_relevant_docs"] += len(retrieved_docs & relevant_docs)
        else:
            stats["queries_without_judgements"] += 1

    return stats
