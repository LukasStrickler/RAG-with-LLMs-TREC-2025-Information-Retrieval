"""
KPI analyzer for comparing metrics against targets.
"""

from rich import box
from rich.console import Console
from rich.table import Table

from eval_cli.config import Config
from eval_cli.models.reports import (
    EvaluationReport,
    MetricValue,
    OverallStatus,
)


class KPIAnalyzer:
    """Analyze system-wide metrics against KPI targets."""

    def __init__(self, config: Config):
        self.config = config
        self.targets = config.metrics.targets

    def analyze_metrics(self, metrics: dict[str, float]) -> list[MetricValue]:
        """Analyze system-wide metrics against targets.

        Metrics dictionary should contain overall system metrics from trec_eval, e.g.:
        - 'all': overall nDCG@10 across all queries
        - Key system KPIs: ndcg_cut_10, map_cut_100, recip_rank, etc.
        """
        metric_values = []

        # Focus on the key system metrics
        key_metrics = {
            "ndcg_cut_10": "nDCG@10",
            "ndcg_cut_25": "nDCG@25",
            "ndcg_cut_50": "nDCG@50",
            "ndcg_cut_100": "nDCG@100",
            "map_cut_100": "MAP@100",
            "recip_rank": "MRR@10",
            "recall_25": "Recall@25",
            "recall_50": "Recall@50",
            "recall_100": "Recall@100",
            "hitrate_10": "HitRate@10",
        }

        for metric_name, display_name in key_metrics.items():
            value = metrics.get(metric_name, metrics.get(f"all.{metric_name}", 0.0))
            target = self.targets.get(metric_name)

            # Determine status
            if target is None:
                status = "unknown"
            elif value >= target:
                status = "pass"
            elif value >= target * 0.9:  # Within 10% of target
                status = "warn"
            else:
                status = "fail"

            metric_value = MetricValue(
                name=display_name,
                value=value,
                target=target,
                status=status,
                higher_is_better=True,
            )
            metric_values.append(metric_value)

        return metric_values

    def create_report(self, metrics: dict[str, float]) -> EvaluationReport:
        """Create evaluation report."""
        metric_values = self.analyze_metrics(metrics)

        # Count statuses
        status_counts = {"pass": 0, "warn": 0, "fail": 0, "unknown": 0}
        for mv in metric_values:
            status_counts[mv.status] += 1

        return EvaluationReport(
            metrics=metric_values,
            status_counts=status_counts,
            overall_status=self._determine_overall_status(status_counts),
        )

    def _determine_overall_status(self, status_counts: dict[str, int]) -> OverallStatus:
        """Determine overall evaluation status."""
        if status_counts["fail"] > 0:
            return "fail"
        elif status_counts["warn"] > 0:
            return "warn"
        elif status_counts["pass"] > 0:
            return "pass"
        else:
            return "unknown"

    def print_summary(self, report: EvaluationReport) -> None:
        """Print KPI summary table."""
        console = Console()

        table = Table(
            title="KPI Analysis Summary",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="white", justify="right")
        table.add_column("Target", style="blue", justify="right")
        table.add_column("Status", justify="center")
        table.add_column("Delta", style="white", justify="right")

        for metric in report.metrics:
            delta = ""
            if metric.target is not None:
                delta = f"{metric.value - metric.target:+.3f}"

            status_symbol = {
                "pass": "✓",
                "warn": "⚠",
                "fail": "✗",
                "unknown": "?",
            }.get(metric.status, "?")

            table.add_row(
                metric.name,
                f"{metric.value:.3f}",
                f"{metric.target:.3f}" if metric.target else "N/A",
                status_symbol,
                delta,
            )

        console.print(table)

        # Overall status
        status_colors = {
            "pass": "green",
            "warn": "yellow",
            "fail": "red",
            "unknown": "white",
        }

        color = status_colors.get(report.overall_status, "white")
        console.print(
            f"\n[bold {color}]"
            f"Overall Status: {report.overall_status.upper()}"
            f"[/bold {color}]"
        )
