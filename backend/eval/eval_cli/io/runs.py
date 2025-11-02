"""
TREC run building and I/O utilities.
"""

import logging
from pathlib import Path

from shared.retrieval.response import QueryResult

from eval_cli.models.runs import RunMetadata, TrecRun, TrecRunRow

logger = logging.getLogger(__name__)


def build_trec_run(
    responses: dict[str, QueryResult],
    run_id: str,
    metadata: RunMetadata,
) -> TrecRun:
    """Convert retrieval responses to TREC run."""
    rows = []

    for query_id, query_result in responses.items():
        # Extract segments from QueryResult
        for rank, segment in enumerate(query_result.segments[:100], start=1):
            row = TrecRunRow(
                query_id=query_id,
                doc_id=segment.segment_id,
                rank=rank,
                score=segment.score,
                run_id=run_id,
            )
            rows.append(row)

    return TrecRun(rows=rows, metadata=metadata)


def write_trec_run(run: TrecRun, output_path: Path) -> None:
    """Write TREC run to TSV file."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Failed to create output directory for {output_path}: {e}")

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for row in run.rows:
                f.write(row.to_trec_line() + "\n")
        logger.info(
            f"Successfully wrote TREC run to {output_path} with {len(run.rows)} rows"
        )
    except OSError as e:
        raise RuntimeError(f"Failed to write run file to {output_path}: {e}")


def read_trec_run(file_path: Path, run_id: str = "unknown") -> TrecRun:
    """Read TREC run from TSV file."""
    rows = []
    skipped_lines = 0
    try:
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                parts = line.strip().split("\t")
                if len(parts) != 6:
                    skipped_lines += 1
                    logger.warning(
                        f"Skipping malformed line {line_num} in {file_path}: "
                        f"expected 6 columns, got {len(parts)}. Line: {line[:100]}"
                    )
                    continue
                try:
                    row = TrecRunRow(
                        query_id=parts[0],
                        q0=parts[1],
                        doc_id=parts[2],
                        rank=int(parts[3]),
                        score=float(parts[4]),
                        run_id=parts[5],
                    )
                    rows.append(row)
                except (ValueError, IndexError) as e:
                    skipped_lines += 1
                    logger.warning(
                        f"Skipping malformed line {line_num} in {file_path}: {e}. "
                        f"Line: {line[:100]}"
                    )
                    continue
    except FileNotFoundError:
        raise FileNotFoundError(f"Run file not found: {file_path}")
    except OSError as e:
        raise RuntimeError(f"Error reading run file {file_path}: {e}")

    # Log summary if lines were skipped
    if skipped_lines > 0:
        logger.warning(
            f"Skipped {skipped_lines} malformed line(s) while reading {file_path}. "
            f"Successfully parsed {len(rows)} rows."
        )

    # Compute top_k from actual data (max rank across all rows)
    top_k = max((row.rank for row in rows), default=0) if rows else 0

    # Create minimal metadata
    metadata = RunMetadata(
        run_id=run_id,
        config_snapshot={},
        topic_source=str(file_path),
        retrieval_mode="unknown",
        top_k=top_k,
        num_queries=len(set(row.query_id for row in rows)),
    )

    return TrecRun(rows=rows, metadata=metadata)
