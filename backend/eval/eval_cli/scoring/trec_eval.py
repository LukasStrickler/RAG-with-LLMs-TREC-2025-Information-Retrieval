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
        """Run trec_eval and parse results."""
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

        # Build command
        cmd = [str(self.binary_path)] + self.config.trec_eval.flags

        for metric in metrics:
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
            logger.info(
                f"trec_eval binary not found at {self.binary_path}, "
                f"falling back to pytrec_eval. Metrics: {metrics}"
            )
            return self._fallback_evaluate(qrels_path, run_path, metrics)

    def _fallback_evaluate(
        self,
        qrels_path: Path,
        run_path: Path,
        metrics: list[str],
    ) -> dict[str, float]:
        """Fallback to pytrec_eval if binary not found.

        pytrec_eval returns results in the format:
        {query_id: {metric_name: score}}

        We need to transpose to:
        {metric_name: mean(per_query_scores)}
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
                            system_metrics[metric_name] = np.mean(valid_scores)
                        else:
                            logger.warning(
                                f"No valid scores for metric '{metric_name}' "
                                f"after filtering {len(scores)} total scores"
                            )
                            system_metrics[metric_name] = np.nan
                    else:
                        system_metrics[metric_name] = np.nan

                return system_metrics

        except OSError as e:
            raise RuntimeError(
                f"Error opening files for evaluation: {e}. "
                f"qrels_path={qrels_path}, run_path={run_path}"
            ) from e

    def _parse_output(self, output: str) -> dict[str, float]:
        """Parse trec_eval output.

        trec_eval outputs lines like:
        'ndcg_cut_10    all    0.3456'
        'ndcg_cut_10    2024-145979    0.4613'
        ...

        We want to extract the 'all' (system-wide) metrics.
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
                        metrics[metric_name] = value

        return metrics
