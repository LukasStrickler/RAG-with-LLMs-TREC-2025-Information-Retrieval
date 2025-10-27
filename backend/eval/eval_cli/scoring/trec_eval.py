"""
trec_eval wrapper for scoring TREC runs.
"""

import subprocess
from pathlib import Path

import numpy as np
import pytrec_eval

from eval_cli.config import Config


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

        if metrics is None:
            metrics = self.config.trec_eval.metrics

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
            )

            return self._parse_output(result.stdout)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"trec_eval failed: {e.stderr}") from e
        except FileNotFoundError:
            # Fallback to pytrec_eval for developer environments without the binary
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
        with open(qrels_path) as qrels_file, open(run_path) as run_file:
            evaluator = pytrec_eval.RelevanceEvaluator(
                pytrec_eval.parse_qrel(qrels_file),
                metrics,
            )
            run = pytrec_eval.parse_run(run_file)

            # Get per-query scores
            # results format: {query_id: {metric_name: score}}
            results = evaluator.evaluate(run)

            # Transpose to get {metric_name: list of scores across queries}
            metrics_by_name = {}
            for query_id, query_scores in results.items():
                for metric_name, score in query_scores.items():
                    if metric_name not in metrics_by_name:
                        metrics_by_name[metric_name] = []
                    metrics_by_name[metric_name].append(score)

            # Compute system-wide (mean) metrics
            system_metrics = {
                metric_name: np.mean(scores)
                for metric_name, scores in metrics_by_name.items()
            }

            return system_metrics

    def _parse_output(self, output: str) -> dict[str, float]:
        """Parse trec_eval output.

        trec_eval outputs lines like:
        'ndcg_cut_10    all    0.3456'
        'ndcg_cut_10    2024-145979    0.4613'
        ...

        We want to extract the 'all' (system-wide) metrics.
        """
        metrics = {}

        for line in output.strip().split("\n"):
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 3:
                    metric_name = parts[0].strip()
                    query_or_all = parts[1].strip()
                    value = float(parts[2].strip())

                    # Only store the 'all' (system-wide) metrics
                    if query_or_all == "all":
                        metrics[metric_name] = value

        return metrics
