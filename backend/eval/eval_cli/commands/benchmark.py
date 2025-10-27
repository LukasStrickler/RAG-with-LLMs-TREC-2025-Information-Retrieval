"""
Benchmarking commands.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from eval_cli.config import Config
from eval_cli.io.runs import read_trec_run
from eval_cli.models.baselines import BaselineComparison, BaselineRun
from eval_cli.scoring.trec_eval import TrecEvalWrapper

app = typer.Typer(help="Benchmarking commands")
console = Console()


@app.command()
def compare(
    run_file: Path = typer.Argument(..., help="TREC run file to benchmark"),
    year: str = typer.Option("rag24", help="Baseline year (rag24, rag25)"),
) -> None:
    """Compare run against organizer baseline."""
    config = Config.load()

    # Load baseline (not used yet, but loaded for future comparison features)
    baseline_path = config.get_data_path(config.paths.baselines[year])
    read_trec_run(baseline_path, f"{year}_baseline")  # Load for validation

    # Load qrels
    qrels_rel_path = config.paths.qrels.get(year)
    if not qrels_rel_path:
        console.print(
            f"[yellow]No qrels configured for {year}; "
            f"supply --qrels-file to compare[/yellow]"
        )
        raise typer.Exit(code=1)

    qrels_path = config.get_data_path(qrels_rel_path)

    # Score both runs
    trec_eval = TrecEvalWrapper(config)

    run_metrics = trec_eval.evaluate(qrels_path, run_file)
    baseline_metrics = trec_eval.evaluate(qrels_path, baseline_path)

    # Create comparison
    comparison = BaselineComparison(
        run_metrics=run_metrics,
        baselines=[
            BaselineRun(
                year=year,
                name=f"{year}_baseline",
                metrics=baseline_metrics,
            )
        ],
        comparisons={f"{year}_baseline": {}},
    )

    # Compute deltas
    for metric in run_metrics:
        if metric in baseline_metrics:
            delta = run_metrics[metric] - baseline_metrics[metric]
            comparison.comparisons.setdefault(f"{year}_baseline", {})[metric] = delta

    # Print comparison table
    table = Table(title=f"Benchmark Comparison ({year.upper()})")
    table.add_column("Metric", style="cyan")
    table.add_column("Your Run", style="green", justify="right")
    table.add_column("Baseline", style="blue", justify="right")
    table.add_column("Delta", style="white", justify="right")
    table.add_column("% Change", style="yellow", justify="right")

    for metric in run_metrics:
        if metric in baseline_metrics:
            delta = run_metrics[metric] - baseline_metrics[metric]
            pct_change = (
                (delta / baseline_metrics[metric]) * 100
                if baseline_metrics[metric] != 0
                else 0
            )

            table.add_row(
                metric,
                f"{run_metrics[metric]:.3f}",
                f"{baseline_metrics[metric]:.3f}",
                f"{delta:+.3f}",
                f"{pct_change:+.1f}%",
            )

    console.print(table)


@app.command()
def targets():
    """Show KPI targets from documentation."""
    config = Config.load()

    table = Table(title="KPI Targets (from .docs/KPI.md)")
    table.add_column("Metric", style="cyan")
    table.add_column("Target", style="green", justify="right")
    table.add_column("Description", style="white")

    descriptions = {
        "ndcg_cut_10": "Primary leaderboard metric",
        "map_cut_100": "Comprehensive ranking quality",
        "recip_rank": "First relevant hit latency",
        "recall_50": "Coverage within top 50",
        "hitrate_10": "Binary success in top 10",
    }

    for metric, target in config.metrics.targets.items():
        table.add_row(
            metric,
            f"{target:.3f}",
            descriptions.get(metric, ""),
        )

    console.print(table)
