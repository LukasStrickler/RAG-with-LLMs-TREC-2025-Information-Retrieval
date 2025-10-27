"""
Generate retrieval responses via API.
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

app = typer.Typer(help="Generate retrieval responses")
console = Console()


@app.command()
def run(
    topics: str = typer.Argument(..., help="Topic file (rag24, rag25) or path"),
    output: Path = typer.Option(None, help="Output file for responses"),
    top_k: int = typer.Option(100, help="Number of results per query"),
) -> None:
    """Generate retrieval responses for topics via API."""
    config = Config.load()

    # Load topics
    if topics in config.paths.topics:
        topic_path = config.get_data_path(config.paths.topics[topics])
    else:
        topic_path = Path(topics)

    topic_set = load_topics(topic_path)
    console.print(f"[cyan]Loaded {len(topic_set)} topics[/cyan]")

    # Generate responses via API
    client = APIRetrievalClient(config)
    responses = client.retrieve_batch_sync(
        topic_set,
        top_k,
    )

    console.print(f"[green]✓ Generated {len(responses)} responses[/green]")

    # Save responses
    if output is None:
        output = config.get_output_path(f"responses_{topics}.json")

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
