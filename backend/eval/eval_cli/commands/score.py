"""
Scoring and evaluation commands.
"""

import json
import math
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from eval_cli.config import Config
from eval_cli.io.qrels import load_qrels
from eval_cli.io.runs import read_trec_run
from eval_cli.scoring.custom_metrics import compute_hitrate_10
from eval_cli.scoring.kpi_analyzer import KPIAnalyzer
from eval_cli.scoring.trec_eval import TrecEvalWrapper

app = typer.Typer(help="Scoring and evaluation commands")
console = Console()


def _resolve_qrels_file(config: Config, qrels_file: Path | None) -> Path:
    """Resolve qrels file path from config or provided path."""
    if qrels_file is None:
        if "rag24" not in config.paths.qrels:
            console.print("[red]Error: 'rag24' qrels not configured[/red]")
            raise typer.Exit(1)
        qrels_file = config.get_data_path(config.paths.qrels["rag24"])
    return qrels_file


@app.command()
def run(
    run_file: Path = typer.Argument(..., help="TREC run file"),
    qrels_file: Path = typer.Option(None, help="Qrels file (default: rag24)"),
    output: Path = typer.Option(None, help="Output report file"),
) -> None:
    """Score a TREC run."""
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Load qrels
    qrels_file = _resolve_qrels_file(config, qrels_file)

    try:
        qrels, stats = load_qrels(qrels_file)
    except FileNotFoundError:
        console.print(f"[red]Error: Qrels file not found: {qrels_file}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading qrels: {e}[/red]")
        raise typer.Exit(1)
    console.print(f"[cyan]Loaded qrels: {len(qrels.entries)} judgements[/cyan]")
    if stats["malformed"] > 0 or stats["invalid_relevance"] > 0:
        console.print(
            f"[yellow]⚠ Data quality issues: "
            f"{stats['malformed']} malformed lines, "
            f"{stats['invalid_relevance']} invalid relevance values skipped[/yellow]"
        )

    # Load run
    try:
        trec_run = read_trec_run(run_file)
    except FileNotFoundError:
        console.print(f"[red]Error: Run file not found: {run_file}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading run: {e}[/red]")
        raise typer.Exit(1)
    console.print(f"[cyan]Loaded run: {len(trec_run.rows)} results[/cyan]")

    # Run trec_eval
    try:
        trec_eval = TrecEvalWrapper(config)
        metrics = trec_eval.evaluate(qrels_file, run_file)
    except Exception as e:
        console.print(f"[red]Error during evaluation: {e}[/red]")
        raise typer.Exit(1)

    # Compute custom metrics
    hitrate_10 = compute_hitrate_10(trec_run, qrels)

    # Add custom metrics
    metrics["hitrate_10"] = hitrate_10

    console.print(f"[green]✓ Computed {len(metrics)} metrics[/green]")

    # Analyze against KPI targets
    analyzer = KPIAnalyzer(config)
    report = analyzer.create_report(metrics)

    # Print summary
    analyzer.print_summary(report)

    # Save report
    if output is None:
        output = config.get_output_path(f"reports/{run_file.stem}_report.json")

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        console.print(f"[red]Error creating output directory: {e}[/red]")
        raise typer.Exit(1)

    try:
        with open(output, "w") as f:
            json.dump(report.model_dump(), f, indent=2, default=str)
    except OSError as e:
        console.print(f"[red]Error writing output file: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓ Saved report to {output}[/green]")


@app.command()
def compare(
    run1: Path = typer.Argument(..., help="First TREC run file"),
    run2: Path = typer.Argument(..., help="Second TREC run file"),
    qrels_file: Path = typer.Option(None, help="Qrels file (default: rag24)"),
) -> None:
    """Compare two TREC runs."""
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Load qrels
    if qrels_file is None:
        if "rag24" not in config.paths.qrels:
            console.print("[red]Error: 'rag24' qrels not configured[/red]")
            raise typer.Exit(1)
        qrels_file = config.get_data_path(config.paths.qrels["rag24"])

    # Score both runs with separate error handling
    trec_eval = TrecEvalWrapper(config)
    try:
        metrics1 = trec_eval.evaluate(qrels_file, run1)
    except FileNotFoundError as e:
        console.print(f"[red]Error: Qrels file not found: {e}[/red]")
        raise typer.Exit(1)
    except RuntimeError as e:
        console.print(f"[red]Error evaluating run1 ({run1}): {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error evaluating run1 ({run1}): {e}[/red]")
        raise typer.Exit(1)

    try:
        metrics2 = trec_eval.evaluate(qrels_file, run2)
    except FileNotFoundError:
        # Already checked above, but handle anyway
        console.print("[red]Error: Qrels file not found[/red]")
        raise typer.Exit(1)
    except RuntimeError as e:
        console.print(f"[red]Error evaluating run2 ({run2}): {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error evaluating run2 ({run2}): {e}[/red]")
        raise typer.Exit(1)

    # Create comparison table
    table = Table(title="Run Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column("Run 1", style="green", justify="right")
    table.add_column("Run 2", style="blue", justify="right")
    table.add_column("Delta", style="white", justify="right")
    table.add_column("% Change", style="yellow", justify="right")

    for metric in metrics1:
        if metric in metrics2:
            delta = metrics2[metric] - metrics1[metric]
            if metrics1[metric] == 0:
                if delta == 0:
                    pct_change = 0
                    pct_str = "0.0%"
                else:
                    # Undefined/infinite change from zero baseline
                    inf_val = math.copysign(float("inf"), delta)
                    pct_str = "∞" if inf_val > 0 else "-∞"
            else:
                pct_change = (delta / metrics1[metric]) * 100
                pct_str = f"{pct_change:+.1f}%"

            table.add_row(
                metric,
                f"{metrics1[metric]:.3f}",
                f"{metrics2[metric]:.3f}",
                f"{delta:+.3f}",
                pct_str,
            )

    console.print(table)
