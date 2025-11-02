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
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

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
        console.print(f"[cyan]Loaded {len(topic_set)} topics[/cyan]")
    except FileNotFoundError as e:
        console.print(f"[red]Error: Topic file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading topics: {e}[/red]")
        raise typer.Exit(1)

    # Generate responses via API
    try:
        client = APIRetrievalClient(config)
        responses = client.retrieve_batch_sync(
            topic_set,
            mode="hybrid",
            top_k=top_k,
        )
        console.print(f"[green]✓ Generated {len(responses)} responses[/green]")
    except RuntimeError as e:
        console.print(f"[red]API Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error generating responses: {e}[/red]")
        raise typer.Exit(1)

    # Save responses
    if output is None:
        # Sanitize filename
        sanitized_topics = Path(topics).stem.replace("/", "_").replace("\\", "_")
        # Replace any other unsafe characters
        sanitized_topics = "".join(
            c if c.isalnum() or c in "._-" else "_" for c in sanitized_topics
        )
        output = config.get_output_path(f"responses_{sanitized_topics}.json")

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        console.print(f"[red]Error creating output directory: {e}[/red]")
        raise typer.Exit(1)

    # Convert to serializable format
    try:
        responses_json = {qid: resp.model_dump() for qid, resp in responses.items()}

        with open(output, "w", encoding="utf-8") as f:
            json.dump(responses_json, f, indent=2)
        console.print(f"[green]✓ Saved responses to {output}[/green]")
    except OSError as e:
        console.print(f"[red]Error writing output file: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error saving responses: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def baseline(
    year: str = typer.Argument(..., help="Baseline year (rag24, rag25)"),
) -> None:
    """Show organizer baseline statistics."""
    # Validate year argument
    valid_years = ["rag24", "rag25"]
    if year not in valid_years:
        console.print(
            f"[red]Error: Invalid year '{year}'. Valid options: {', '.join(valid_years)}[/red]"
        )
        raise typer.Exit(1)

    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    try:
        loader = BaselineLoader(config)
    except Exception as e:
        console.print(f"[red]Error initializing BaselineLoader: {e}[/red]")
        raise typer.Exit(1)

    try:
        stats = loader.get_baseline_stats(year)

        table = Table(title=f"Organizer Baseline ({year.upper()})")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        for metric, value in stats.items():
            table.add_row(metric.replace("_", " ").title(), str(value))

        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[red]Error: Baseline file not found: {e}[/red]")
        raise typer.Exit(1)
    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading baseline statistics: {e}[/red]")
        raise typer.Exit(1)
