"""
trec_eval wrapper for scoring TREC runs.
"""

import logging
import subprocess
from pathlib import Path

import numpy as np
import pytrec_eval

from eval_cli.config import Config

logger = logging.getLogger(__name__)


class TrecEvalWrapper:
    """Wrapper for trec_eval binary."""

    def __init__(self, config: Config):
        self.config = config
        self.binary_path = config.trec_eval.binary_path

    def evaluate(
        self,
        qrels_path: Path,
        run_path: Path,
        metrics: list[str] | None = None,
    ) -> dict[str, float]:
        """Run trec_eval and parse results.

        Supports both:
        1. trec_eval binary: Groups metrics with comma-separated cutoffs (e.g., 'recall.25,50,100')
        2. pytrec_eval fallback: Uses original format with separate metrics (e.g., ['recall.25', 'recall.50'])

        Both methods produce identical results, just with different input formats.
        """
        # Validate input files exist
        if not qrels_path.exists():
            raise FileNotFoundError(f"Qrels file not found: {qrels_path}")
        if not run_path.exists():
            raise FileNotFoundError(f"Run file not found: {run_path}")

        if metrics is None:
            metrics = self.config.trec_eval.metrics

        # Ensure metrics is never None (fallback to empty list if both are None)
        if metrics is None:
            metrics = []

        # Build command for trec_eval binary
        # Group metrics by base name and combine cutoffs (trec_eval binary requires comma-separated cutoffs)
        # e.g., ['recall.25', 'recall.50', 'recall.100'] -> ['recall.25,50,100']
        # This is ONLY needed for the trec_eval binary, NOT for pytrec_eval fallback
        grouped_metrics = self._group_metrics(metrics)

        cmd = [str(self.binary_path)] + self.config.trec_eval.flags

        for metric in grouped_metrics:
            cmd.extend(["-m", metric])

        cmd.extend([str(qrels_path), str(run_path)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,  # 120 second timeout to avoid indefinite hangs
            )

            return self._parse_output(result.stdout)

        except subprocess.TimeoutExpired as e:
            logger.error(f"trec_eval timed out after 120 seconds: {e}")
            raise RuntimeError(
                "trec_eval timed out after 120 seconds. This may indicate "
                "a problem with the input files or system performance."
            ) from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"trec_eval failed: {e.stderr}") from e
        except FileNotFoundError:
            # Fallback to pytrec_eval for developer environments without the binary
            # Note: pytrec_eval uses the ORIGINAL (ungrouped) metrics format
            # This is different from the binary which requires grouped metrics
            logger.info(
                f"trec_eval binary not found at {self.binary_path}, "
                f"falling back to pytrec_eval. Using original metrics format: {metrics}"
            )
            return self._fallback_evaluate(qrels_path, run_path, metrics)

    def _fallback_evaluate(
        self,
        qrels_path: Path,
        run_path: Path,
        metrics: list[str],
    ) -> dict[str, float]:
        """Fallback to pytrec_eval if binary not found.

        pytrec_eval accepts metrics in the original format (separate flags for each cutoff)
        and returns results in the format:
        {query_id: {metric_name: score}}

        We need to transpose to:
        {metric_name: mean(per_query_scores)}

        Note: pytrec_eval works with separate metric flags (e.g., ['recall.25', 'recall.50']),
        unlike the trec_eval binary which requires comma-separated cutoffs.
        """
        try:
            with (
                open(qrels_path, encoding="utf-8") as qrels_file,
                open(run_path, encoding="utf-8") as run_file,
            ):
                try:
                    qrels_data = pytrec_eval.parse_qrel(qrels_file)
                    run_data = pytrec_eval.parse_run(run_file)
                except Exception as e:
                    raise RuntimeError(
                        f"Error parsing qrels or run file: {e}. "
                        f"qrels_path={qrels_path}, run_path={run_path}"
                    ) from e

                try:
                    # pytrec_eval accepts metrics in original format (not grouped)
                    # It handles multiple cutoffs differently than the binary
                    evaluator = pytrec_eval.RelevanceEvaluator(qrels_data, metrics)
                    results = evaluator.evaluate(run_data)
                except Exception as e:
                    raise RuntimeError(
                        f"Error during pytrec_eval evaluation: {e}. "
                        f"qrels_path={qrels_path}, run_path={run_path}"
                    ) from e

                # Transpose to get {metric_name: list of scores across queries}
                metrics_by_name = {}
                for _query_id, query_scores in results.items():
                    for metric_name, score in query_scores.items():
                        if metric_name not in metrics_by_name:
                            metrics_by_name[metric_name] = []
                        metrics_by_name[metric_name].append(score)

                # Guard against empty results before np.mean
                if not metrics_by_name:
                    logger.warning(
                        "No metrics computed (empty results). Returning empty metrics dict."
                    )
                    return {}

                # Compute system-wide (mean) metrics with defensive parsing
                # Note: pytrec_eval already outputs metric names with underscores (recall_25),
                # so no normalization needed here, but we ensure consistency
                system_metrics = {}
                for metric_name, scores in metrics_by_name.items():
                    if scores:
                        # Filter out invalid values before computing mean
                        valid_scores = []
                        for score in scores:
                            try:
                                score_float = float(score)
                                if not (np.isnan(score_float) or np.isinf(score_float)):
                                    valid_scores.append(score_float)
                            except (ValueError, TypeError) as e:
                                logger.warning(
                                    f"Invalid score value for metric '{metric_name}': "
                                    f"{score} (type: {type(score)}). Error: {e}"
                                )

                        if valid_scores:
                            # Normalize metric names for consistency (pytrec_eval uses underscores,
                            # but we ensure dots are converted to underscores just in case)
                            normalized_name = metric_name.replace(".", "_")
                            system_metrics[normalized_name] = np.mean(valid_scores)
                        else:
                            logger.warning(
                                f"No valid scores for metric '{metric_name}' "
                                f"after filtering {len(scores)} total scores"
                            )
                            normalized_name = metric_name.replace(".", "_")
                            system_metrics[normalized_name] = np.nan
                    else:
                        normalized_name = metric_name.replace(".", "_")
                        system_metrics[normalized_name] = np.nan

                return system_metrics

        except OSError as e:
            raise RuntimeError(
                f"Error opening files for evaluation: {e}. "
                f"qrels_path={qrels_path}, run_path={run_path}"
            ) from e

    def _group_metrics(self, metrics: list[str]) -> list[str]:
        """Group metrics by base name and combine cutoffs.

        trec_eval requires comma-separated cutoffs in a single -m flag.
        For example: ['recall.25', 'recall.50', 'recall.100'] -> ['recall.25,50,100']

        Args:
            metrics: List of metric names (e.g., ['recall.25', 'recall.50', 'ndcg_cut.10'])

        Returns:
            List of grouped metric names with comma-separated cutoffs
        """
        # Group metrics by base name (everything before the last dot)
        groups: dict[str, list[str]] = {}
        standalone: list[str] = []

        for metric in metrics:
            if "." in metric:
                # Has a cutoff parameter
                base, cutoff = metric.rsplit(".", 1)
                if base not in groups:
                    groups[base] = []
                groups[base].append(cutoff)
            else:
                # No cutoff, standalone metric
                standalone.append(metric)

        # Combine cutoffs for each base metric
        grouped = []
        for base, cutoffs in groups.items():
            # Sort cutoffs numerically
            try:
                cutoffs_sorted = sorted(cutoffs, key=lambda x: int(x))
            except ValueError:
                # If not numeric, sort as strings
                cutoffs_sorted = sorted(cutoffs)
            grouped.append(f"{base}.{','.join(cutoffs_sorted)}")

        # Add standalone metrics
        grouped.extend(standalone)

        return grouped

    def _parse_output(self, output: str) -> dict[str, float]:
        """Parse trec_eval output.

        trec_eval outputs lines like:
        'ndcg_cut_10    all    0.3456'
        'ndcg_cut_10    2024-145979    0.4613'
        'recall.25      all    0.3456'  (note: trec_eval uses dots)
        ...

        We want to extract the 'all' (system-wide) metrics.
        Normalize metric names by converting dots to underscores for consistency.
        """
        metrics = {}

        for line_num, line in enumerate(output.strip().splitlines(), 1):
            if not line.strip():
                continue
            parts = line.split(maxsplit=2)
            if len(parts) >= 3:
                metric_name = parts[0].strip()
                query_or_all = parts[1].strip()
                try:
                    value = float(parts[2].strip())
                except ValueError as e:
                    logger.warning(
                        f"Malformed numeric value in trec_eval output line {line_num}: "
                        f"metric={metric_name}, raw_value='{parts[2].strip()}', error={e}"
                    )
                    continue

                # Only store the 'all' (system-wide) metrics
                if query_or_all == "all":
                    # Normalize metric names: trec_eval binary uses dots (recall.25),
                    # but we standardize to underscores (recall_25) for consistency
                    normalized_name = metric_name.replace(".", "_")
                    metrics[normalized_name] = value
                    logger.debug(
                        f"Parsed metric: {metric_name} -> {normalized_name} = {value}"
                    )

        if not metrics:
            logger.warning(
                "No metrics found in trec_eval output. This may indicate a parsing issue."
            )
        else:
            logger.debug(f"Parsed {len(metrics)} metrics: {list(metrics.keys())}")

        return metrics
