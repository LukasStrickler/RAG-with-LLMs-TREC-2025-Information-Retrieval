"""
End-to-end evaluation pipeline commands.
"""

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from eval_cli.client import APIRetrievalClient
from eval_cli.config import Config
from eval_cli.io.runs import build_trec_run, write_trec_run
from eval_cli.io.topics import load_topics
from eval_cli.models.reports import EvaluationReport
from eval_cli.models.runs import RunMetadata
from eval_cli.scoring.kpi_analyzer import KPIAnalyzer
from eval_cli.scoring.trec_eval import TrecEvalWrapper

app = typer.Typer(help="End-to-end evaluation pipeline")
console = Console()

# Metric mapping for comparisons: {display_name: metric_key}
COMPARISON_METRICS = {
    "ndcg_10": "ndcg_cut_10",
    "map_100": "map_cut_100",
    "mrr_10": "recip_rank",  # Note: recip_rank_cut_10 may also be used
}


def generate_experiment_name(
    topics: str, mode: str | None = None, experiment_id: str | None = None
) -> str:
    """Generate a unique experiment name with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    base_name = f"{experiment_id}_{topics}" if experiment_id else topics

    if mode:
        base_name = f"{base_name}_{mode}"

    return f"{base_name}_{timestamp}"


@app.command()
def run(
    topics: str = typer.Argument(..., help="Topic file (rag24, rag25) or path"),
    mode: str = typer.Option("hybrid", help="Retrieval mode: lexical, vector, hybrid"),
    experiment_id: str = typer.Option(None, help="Experiment identifier (optional)"),
    output_dir: Path = typer.Option(None, help="Output directory"),
    top_k: int = typer.Option(100, help="Number of results per query"),
) -> None:
    """
    Run complete evaluation pipeline for a retrieval mode.

    This will:
    1. Load topics
    2. Generate retrieval responses via API
    3. Build TREC run file
    4. Compute all metrics (nDCG, MAP, MRR, Recall, Precision)
    5. Analyze KPIs against competition targets
    6. Save all outputs (run file, scores, analysis)

    Results are saved with timestamped experiment names for easy comparison.
    """
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Generate unique experiment name
    experiment_name = generate_experiment_name(topics, mode, experiment_id)

    if output_dir is None:
        output_dir = config.get_output_path(f"experiments/{experiment_name}")

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]🧪 Experiment: {experiment_name}[/bold cyan]")
    console.print(f"[dim]Output directory: {output_dir}[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Load topics
        task1 = progress.add_task("Loading topics...", total=None)
        try:
            if topics in config.paths.topics:
                topic_path = config.get_data_path(config.paths.topics[topics])
            else:
                topic_path = Path(topics)

            if not topic_path.exists():
                console.print(f"[red]Error: Topic file not found: {topic_path}[/red]")
                raise typer.Exit(1)

            topic_set = load_topics(topic_path)
            progress.update(task1, description=f"Loaded {len(topic_set)} topics")
        except FileNotFoundError as e:
            console.print(f"[red]Error: Topic file not found: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error loading topics: {e}[/red]")
            raise typer.Exit(1)

        # Step 2: Generate responses via API
        task2 = progress.add_task("Generating responses via API...", total=None)
        try:
            client = APIRetrievalClient(config)
            responses = client.retrieve_batch_sync(topic_set, mode, top_k)
            progress.update(task2, description=f"Generated {len(responses)} responses")
        except RuntimeError as e:
            console.print(f"[red]API Error: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error generating responses: {e}[/red]")
            raise typer.Exit(1)

        # Step 3: Build TREC run
        task3 = progress.add_task("Building TREC run...", total=None)
        run_id = experiment_name  # Use experiment name as run_id
        metadata = RunMetadata(
            run_id=run_id,
            config_snapshot=config.model_dump(),
            topic_source=str(topic_path),
            retrieval_mode=mode,
            top_k=top_k,
            num_queries=len(topic_set),
        )

        try:
            trec_run = build_trec_run(responses, run_id, metadata)
            run_file = output_dir / f"{run_id}.tsv"
            write_trec_run(trec_run, run_file)
            progress.update(task3, description=f"Built TREC run: {run_file}")
        except Exception as e:
            console.print(f"[red]Error building/writing TREC run: {e}[/red]")
            raise typer.Exit(1)

        # Step 4: Score run
        task4 = progress.add_task("Scoring run...", total=None)
        qrels_rel_path = config.paths.qrels.get(topics)
        if not qrels_rel_path:
            available = list(config.paths.qrels.keys())
            raise RuntimeError(
                f"No qrels configured for topics='{topics}'. " f"Available: {available}"
            )
        qrels_path = config.get_data_path(qrels_rel_path)
        try:
            trec_eval = TrecEvalWrapper(config)
            metrics = trec_eval.evaluate(qrels_path, run_file)
            progress.update(task4, description=f"Computed {len(metrics)} metrics")
        except FileNotFoundError as e:
            console.print(f"[red]Error: Qrels file not found: {e}[/red]")
            raise typer.Exit(1)
        except RuntimeError as e:
            console.print(f"[red]Error during evaluation: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error computing metrics: {e}[/red]")
            raise typer.Exit(1)

        # Step 5: Analyze KPIs
        task5 = progress.add_task("Analyzing KPIs...", total=None)
        analyzer = KPIAnalyzer(config)
        report = analyzer.create_report(metrics)
        progress.update(task5, description="KPI analysis complete")

    # Print results
    console.print("\n[bold green]Pipeline Complete![/bold green]")
    console.print(f"Output directory: {output_dir}")

    # Show KPI summary
    analyzer.print_summary(report)

    # Save report
    report_file = output_dir / f"{run_id}_report.json"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2, default=str)
        console.print(f"\n[green]✓ Report saved: {report_file}[/green]")
    except OSError as e:
        console.print(f"[red]Error writing report file: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error saving report: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def benchmark(
    topics: str = typer.Argument(..., help="Topic file (rag24, rag25) or path"),
    output_dir: Path = typer.Option(None, help="Output directory"),
) -> None:
    """Run pipeline with all performance levels and compare."""
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    if output_dir is None:
        output_dir = config.get_output_path(f"benchmarks/{topics}")

    output_dir.mkdir(parents=True, exist_ok=True)

    def run_pipeline_for_level(level: str) -> tuple[dict[str, float], EvaluationReport]:
        """Helper that mirrors pipeline.run logic for reuse."""
        run_dir = output_dir / level
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            if topics in config.paths.topics:
                topic_path = config.get_data_path(config.paths.topics[topics])
            else:
                topic_path = Path(topics)

            if not topic_path.exists():
                raise FileNotFoundError(f"Topic file not found: {topic_path}")

            topic_set = load_topics(topic_path)
            client = APIRetrievalClient(config)
            # Note: performance_level is not supported by APIRetrievalClient
            # This may need to be handled differently for mock scenarios
            responses = client.retrieve_batch_sync(topic_set, mode="hybrid", top_k=100)
        except FileNotFoundError as e:
            raise RuntimeError(f"Error loading topics: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Error in pipeline execution: {e}") from e

        run_id = f"benchmark_{topics}_{level}"
        metadata = RunMetadata(
            run_id=run_id,
            config_snapshot=config.model_dump(),
            topic_source=str(topic_path),
            retrieval_mode="mock",
            top_k=100,
            num_queries=len(topic_set),
            performance_level=level,
        )

        try:
            trec_run = build_trec_run(responses, run_id, metadata)
            run_file = run_dir / f"{run_id}.tsv"
            write_trec_run(trec_run, run_file)
        except Exception as e:
            raise RuntimeError(f"Error building/writing TREC run: {e}") from e

        qrels_rel_path = config.paths.qrels.get(topics)
        if not qrels_rel_path:
            available = list(config.paths.qrels.keys())
            raise RuntimeError(
                f"No qrels configured for topics='{topics}'. " f"Available: {available}"
            )
        qrels_path = config.get_data_path(qrels_rel_path)
        try:
            trec_eval = TrecEvalWrapper(config)
            metrics = trec_eval.evaluate(qrels_path, run_file)
            analyzer = KPIAnalyzer(config)
            report = analyzer.create_report(metrics)
            analyzer.print_summary(report)
        except (FileNotFoundError, RuntimeError) as e:
            raise RuntimeError(f"Error during evaluation: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error computing metrics: {e}") from e

        report_file = run_dir / f"{run_id}_report.json"
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report.model_dump(), f, indent=2, default=str)
        except OSError as e:
            raise RuntimeError(f"Error writing report file: {e}") from e

        return metrics, report

    # Run all performance levels
    results = {}
    for level in config.mock.performance_levels:
        console.print(f"\n[cyan]Running {level} performance level...[/cyan]")
        try:
            metrics, _ = run_pipeline_for_level(level)
            results[level] = {
                display_name: metrics.get(metric_key, 0.0)
                for display_name, metric_key in COMPARISON_METRICS.items()
            }
        except Exception as e:
            console.print(f"[red]Error running {level} performance level: {e}[/red]")
            raise typer.Exit(1)

    # Create comparison table
    table = Table(title="Performance Level Comparison")
    table.add_column("Level", style="cyan")
    table.add_column("nDCG@10", style="green", justify="right")
    table.add_column("MAP@100", style="blue", justify="right")
    table.add_column("MRR@10", style="yellow", justify="right")

    for level, metrics in results.items():
        table.add_row(
            level.title(),
            f"{metrics['ndcg_10']:.3f}",
            f"{metrics['map_100']:.3f}",
            f"{metrics['mrr_10']:.3f}",
        )

    console.print(table)


@app.command("run-all")
def run_all_modes(
    topics: str = typer.Argument(..., help="Topic file (rag24, rag25)"),
    experiment_id: str = typer.Option(None, help="Experiment identifier (optional)"),
    output_dir: Path = typer.Option(None, help="Output directory for results"),
    top_k: int = typer.Option(100, help="Number of results per query (default: 100)"),
) -> None:
    """
    Run evaluation pipeline for ALL retrieval modes (lexical, vector, hybrid).

    Generates runs for each mode and produces comparative analysis.
    Results are saved with timestamped experiment names for easy comparison.
    """
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)
    modes = ["lexical", "vector", "hybrid"]

    # Generate unique experiment name for the entire run
    experiment_name = generate_experiment_name(topics, experiment_id=experiment_id)

    # Set output directory
    if output_dir is None:
        output_dir = config.get_output_path(f"experiments/{experiment_name}")

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]🧪 Multi-Mode Experiment: {experiment_name}[/bold cyan]")
    console.print(f"[dim]Output directory: {output_dir}[/dim]\n")

    results = {}

    for mode in modes:
        console.print(f"[bold cyan]🔄 Running {mode.upper()} Mode...[/bold cyan]")

        # Generate mode-specific experiment name
        mode_experiment_name = f"{experiment_name}_{mode}"

        # Run pipeline for this mode
        run_id = mode_experiment_name
        mode_output_dir = output_dir / mode

        # Load topics
        try:
            if topics in config.paths.topics:
                topic_path = config.get_data_path(config.paths.topics[topics])
            else:
                topic_path = Path(topics)

            if not topic_path.exists():
                console.print(f"[red]Error: Topic file not found: {topic_path}[/red]")
                raise typer.Exit(1)

            topic_set = load_topics(topic_path)
            client = APIRetrievalClient(config)
            responses = client.retrieve_batch_sync(topic_set, mode, top_k)
        except FileNotFoundError as e:
            console.print(f"[red]Error: Topic file not found: {e}[/red]")
            raise typer.Exit(1)
        except RuntimeError as e:
            console.print(f"[red]API Error: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(
                f"[red]Error loading topics or generating responses: {e}[/red]"
            )
            raise typer.Exit(1)

        metadata = RunMetadata(
            run_id=run_id,
            config_snapshot=config.model_dump(),
            topic_source=str(topic_path),
            retrieval_mode=mode,
            top_k=top_k,
            num_queries=len(topic_set),
        )

        try:
            trec_run = build_trec_run(responses, run_id, metadata)
            run_file = mode_output_dir / f"{run_id}.tsv"
            mode_output_dir.mkdir(parents=True, exist_ok=True)
            write_trec_run(trec_run, run_file)
        except Exception as e:
            console.print(f"[red]Error building/writing TREC run for {mode}: {e}[/red]")
            raise typer.Exit(1)

        # Score
        qrels_rel_path = config.paths.qrels.get(topics)
        if not qrels_rel_path:
            available = list(config.paths.qrels.keys())
            console.print(
                f"[red]No qrels configured for topics='{topics}'. Available: {available}[/red]"
            )
            raise typer.Exit(1)
        qrels_path = config.get_data_path(qrels_rel_path)
        try:
            trec_eval = TrecEvalWrapper(config)
            metrics = trec_eval.evaluate(qrels_path, run_file)

            # Analyze KPIs
            analyzer = KPIAnalyzer(config)
            report = analyzer.create_report(metrics)
        except FileNotFoundError as e:
            console.print(f"[red]Error: Qrels file not found: {e}[/red]")
            raise typer.Exit(1)
        except RuntimeError as e:
            console.print(f"[red]Error during evaluation for {mode}: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error computing metrics for {mode}: {e}[/red]")
            raise typer.Exit(1)

        # Save KPI report
        report_file = mode_output_dir / f"{run_id}_report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report.model_dump(), f, indent=2, default=str)
        except OSError as e:
            console.print(f"[red]Error writing report file for {mode}: {e}[/red]")
            raise typer.Exit(1)

        # Save results
        results[mode] = {
            "run_file": run_file,
            "metrics": metrics,
            "kpi_report": report.model_dump(),
            "run_id": run_id,
        }

        console.print(f"[green]✓ {mode.upper()} completed[/green]")

    # Generate comparison report
    console.print("[bold cyan]📊 Generating comparison report...[/bold cyan]")

    comparison_file = output_dir / f"{experiment_name}_comparison.json"
    try:
        with open(comparison_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
    except OSError as e:
        console.print(f"[red]Error writing comparison file: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error saving comparison: {e}[/red]")
        raise typer.Exit(1)

    console.print("[bold green]✅ All modes completed[/bold green]")
    console.print(f"[cyan]📁 Output directory:[/cyan] {output_dir}")
    console.print(f"[cyan]📊 Comparison file:[/cyan] {comparison_file}")

    # Display summary table
    table = Table(title=f"Retrieval Mode Comparison ({topics.upper()})")
    table.add_column("Mode", style="cyan")
    table.add_column("nDCG@10", style="green")
    table.add_column("MAP@100", style="green")
    table.add_column("MRR@10", style="green")

    for mode, data in results.items():
        metrics = data["metrics"]
        table.add_row(
            mode.title(),
            f"{metrics.get(COMPARISON_METRICS['ndcg_10'], 0):.3f}",
            f"{metrics.get(COMPARISON_METRICS['map_100'], 0):.3f}",
            f"{metrics.get(COMPARISON_METRICS['mrr_10'], 0):.3f}",
        )

    console.print(table)


@app.command("list")
def list_experiments(
    topics: str = typer.Option(None, help="Filter by topics (rag24, rag25)"),
    mode: str = typer.Option(None, help="Filter by mode (lexical, vector, hybrid)"),
) -> None:
    """
    List all available experiments for comparison.

    Shows experiment names, timestamps, and basic info for easy comparison.
    """
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)
    experiments_dir = config.get_output_path("experiments")

    if not experiments_dir.exists():
        console.print(
            "[yellow]No experiments found. Run some evaluations first![/yellow]"
        )
        return

    console.print("[bold cyan]📋 Available Experiments[/bold cyan]")
    console.print(f"[dim]Experiments directory: {experiments_dir}[/dim]\n")

    experiments = []

    # Find all experiment directories
    for exp_dir in experiments_dir.iterdir():
        if exp_dir.is_dir():
            exp_name = exp_dir.name

            # Parse experiment name to extract info
            # Expected format: [topics]_[mode]_[timestamp] (3 parts)
            # or [experiment_id]_[topics]_[mode]_[timestamp] (4 parts)
            parts = exp_name.split("_")
            if len(parts) in (3, 4):
                if len(parts) == 4:
                    exp_id, exp_topics, exp_mode, timestamp = parts
                else:
                    exp_id = None
                    exp_topics, exp_mode, timestamp = parts
            else:
                # Unexpected format - warn and skip
                console.print(
                    f"[dim yellow]Warning: Skipping experiment '{exp_name}' - "
                    f"unexpected format (expected 3 or 4 underscore-separated parts, got {len(parts)})[/dim yellow]"
                )
                continue

            # Apply filters
            if topics and exp_topics != topics:
                continue
            if mode and exp_mode != mode:
                continue

            # Parse timestamp
            try:
                exp_time = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                experiments.append(
                    {
                        "name": exp_name,
                        "id": exp_id,
                        "topics": exp_topics,
                        "mode": exp_mode,
                        "timestamp": exp_time,
                        "path": exp_dir,
                    }
                )
            except ValueError:
                continue

    if not experiments:
        console.print("[yellow]No experiments match the filters.[/yellow]")
        return

    # Sort by timestamp (newest first)
    experiments.sort(key=lambda x: x["timestamp"], reverse=True)

    # Display experiments
    table = Table(title="Available Experiments")
    table.add_column("Experiment", style="cyan")
    table.add_column("Topics", style="green")
    table.add_column("Mode", style="blue")
    table.add_column("Timestamp", style="yellow")
    table.add_column("Files", style="dim")

    for exp in experiments:
        # Count files in experiment
        files = list(exp["path"].rglob("*.tsv")) + list(exp["path"].rglob("*.json"))
        file_count = len(files)

        table.add_row(
            exp["name"],
            exp["topics"],
            exp["mode"],
            exp["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            f"{file_count} files",
        )

    console.print(table)

    if experiments:
        console.print(
            "\n[dim]Use 'eval pipeline compare <experiment1> <experiment2>' "
            "to compare experiments[/dim]"
        )


@app.command("compare")
def compare_experiments(
    exp1: str = typer.Argument(..., help="First experiment name"),
    exp2: str = typer.Argument(..., help="Second experiment name"),
) -> None:
    """
    Compare two experiments side by side.

    Shows metrics comparison between two experiments for easy analysis.
    """
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)
    experiments_dir = config.get_output_path("experiments")

    exp1_path = experiments_dir / exp1
    exp2_path = experiments_dir / exp2

    if not exp1_path.exists():
        console.print(f"[red]❌ Experiment '{exp1}' not found[/red]")
        return

    if not exp2_path.exists():
        console.print(f"[red]❌ Experiment '{exp2}' not found[/red]")
        return

    console.print("[bold cyan]🔍 Comparing Experiments[/bold cyan]")
    console.print(f"[cyan]Experiment 1:[/cyan] {exp1}")
    console.print(f"[cyan]Experiment 2:[/cyan] {exp2}\n")

    # Find comparison files
    exp1_comparison = None
    exp2_comparison = None

    for comp_file in exp1_path.rglob("*_comparison.json"):
        exp1_comparison = comp_file
        break

    for comp_file in exp2_path.rglob("*_comparison.json"):
        exp2_comparison = comp_file
        break

    if not exp1_comparison or not exp2_comparison:
        console.print(
            "[yellow]⚠️  Comparison files not found. "
            "Run 'run-all' command to generate them.[/yellow]"
        )
        return

    # Load comparison data
    try:
        with open(exp1_comparison, encoding="utf-8") as f:
            exp1_data = json.load(f)
        with open(exp2_comparison, encoding="utf-8") as f:
            exp2_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error: Comparison file not found: {e}[/red]")
        raise typer.Exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON in comparison file: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading comparison files: {e}[/red]")
        raise typer.Exit(1)

    # Create comparison table
    table = Table(title="Experiment Comparison")
    table.add_column("Mode", style="cyan")
    table.add_column(f"{exp1}", style="green")
    table.add_column(f"{exp2}", style="blue")
    table.add_column("Difference", style="yellow")

    # Compare metrics for each mode
    modes = ["lexical", "vector", "hybrid"]
    for mode in modes:
        if mode in exp1_data and mode in exp2_data:
            exp1_metrics = exp1_data[mode].get("metrics", {})
            exp2_metrics = exp2_data[mode].get("metrics", {})

            # Compare nDCG@10 as example
            ndcg_key = COMPARISON_METRICS["ndcg_10"]
            exp1_ndcg = exp1_metrics.get(ndcg_key, 0)
            exp2_ndcg = exp2_metrics.get(ndcg_key, 0)
            diff = exp2_ndcg - exp1_ndcg

            table.add_row(
                mode.title(),
                f"{exp1_ndcg:.4f}",
                f"{exp2_ndcg:.4f}",
                f"{diff:+.4f}" if diff != 0 else "0.0000",
            )

    console.print(table)
