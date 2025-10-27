"""
Custom metrics for evaluation.
"""

from eval_cli.io.qrels import Qrels
from eval_cli.models.runs import TrecRun


def compute_hitrate_10(trec_run: TrecRun, qrels: Qrels) -> float:
    """Compute HitRate@10 (binary success in top 10)."""
    if not trec_run.rows:
        return 0.0

    successful_queries = 0
    total_queries = 0

    # Group run rows by query
    query_results = {}
    for row in trec_run.rows:
        if row.query_id not in query_results:
            query_results[row.query_id] = []
        query_results[row.query_id].append(row)

    for query_id, results in query_results.items():
        # Get top 10 results
        top_10_docs = {row.doc_id for row in sorted(results, key=lambda x: x.rank)[:10]}

        # Check if any relevant doc is in top 10
        relevant_docs = qrels.get_relevant_docs(query_id)

        if relevant_docs and (top_10_docs & relevant_docs):
            successful_queries += 1

        total_queries += 1

    return successful_queries / total_queries if total_queries > 0 else 0.0


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
    query_results = {}
    for row in trec_run.rows:
        if row.query_id not in query_results:
            query_results[row.query_id] = []
        query_results[row.query_id].append(row)

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
