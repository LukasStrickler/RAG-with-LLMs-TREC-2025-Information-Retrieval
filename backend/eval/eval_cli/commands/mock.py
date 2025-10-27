"""
Mock retrieval system commands.
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from eval_cli.client import APIRetrievalClient
from eval_cli.config import Config
from eval_cli.io.topics import load_topics
from eval_cli.mock.baseline_loader import BaselineLoader

app = typer.Typer(help="Mock retrieval system commands")
console = Console()


@app.command()
def generate(
    topics: str = typer.Argument(..., help="Topic file (rag24, rag25) or path"),
    output: Path = typer.Option(None, help="Output file for responses"),
    performance: str = typer.Option(
        "baseline", help="Performance level (poor, baseline, good, strong)"
    ),
    top_k: int = typer.Option(100, help="Number of results per query"),
) -> None:
    """Generate mock retrieval responses via API."""
    config = Config.load()

    # Load topics
    if topics in config.paths.topics:
        topic_path = config.get_data_path(config.paths.topics[topics])
    else:
        topic_path = Path(topics)

    topic_set = load_topics(topic_path)
    console.print(f"[cyan]Loaded {len(topic_set)} topics[/cyan]")

    # Generate mock responses via API
    client = APIRetrievalClient(config)
    responses = client.retrieve_batch_sync(
        topic_set,
        performance,
        top_k,
    )

    console.print(f"[green]✓ Generated {len(responses)} mock responses via API[/green]")

    # Save responses
    if output is None:
        output = config.get_output_path(f"mock_responses_{topics}_{performance}.json")

    output.parent.mkdir(parents=True, exist_ok=True)

    # Convert to serializable format
    responses_json = {qid: resp.model_dump() for qid, resp in responses.items()}

    with open(output, "w") as f:
        json.dump(responses_json, f, indent=2)

    console.print(f"[green]✓ Saved responses to {output}[/green]")


@app.command()
def baseline(
    year: str = typer.Argument(..., help="Baseline year (rag24, rag25)"),
) -> None:
    """Show organizer baseline statistics."""
    config = Config.load()
    loader = BaselineLoader(config)

    try:
        stats = loader.get_baseline_stats(year)

        table = Table(title=f"Organizer Baseline ({year.upper()})")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        for metric, value in stats.items():
            table.add_row(metric.replace("_", " ").title(), str(value))

        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def compare(
    year: str = typer.Argument(..., help="Baseline year (rag24, rag25)"),
) -> None:
    """Compare mock performance levels against baseline."""
    config = Config.load()

    table = Table(title=f"Performance Level Comparison ({year.upper()})")
    table.add_column("Level", style="cyan")
    table.add_column("nDCG@10", style="green")
    table.add_column("MAP@100", style="green")
    table.add_column("MRR@10", style="green")

    for level, targets in config.mock.performance_levels.items():
        table.add_row(
            level.title(),
            f"{targets['ndcg_10']:.3f}",
            f"{targets['map_100']:.3f}",
            f"{targets['mrr_10']:.3f}",
        )

    console.print(table)
