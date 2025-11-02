"""
Topic management commands.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from eval_cli.config import Config
from eval_cli.io.topics import load_topics

app = typer.Typer(help="Topic management commands")
console = Console()


def _resolve_topic_file_path(file: str, config: Config) -> Path:
    """Resolve topic file path from config or direct filesystem path."""
    if file in config.paths.topics:
        return config.get_data_path(config.paths.topics[file])
    else:
        return Path(file)


@app.command("list")
def list_topics() -> None:
    """List available topic files."""
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    table = Table(title="Available Topic Files")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Exists", style="yellow")

    for name, rel_path in config.paths.topics.items():
        full_path = config.get_data_path(rel_path)
        exists = "✓" if full_path.exists() else "✗"
        table.add_row(name, str(full_path), exists)

    console.print(table)


@app.command()
def load(
    file: str = typer.Argument(..., help="Topic file name (rag24, rag25) or path"),
) -> None:
    """Load and validate topics."""
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Resolve file path
    if file in config.paths.topics:
        file_path = config.get_data_path(config.paths.topics[file])
    else:
        file_path = Path(file)

    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    # Load topics
    try:
        topic_set = load_topics(file_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error: Topic file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading topics: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓ Loaded {len(topic_set)} topics from {file_path}[/green]")
    console.print(f"Format: {topic_set.format}")

    # Show first few topics
    table = Table(title="Sample Topics")
    table.add_column("ID", style="cyan")
    table.add_column("Query", style="white")
    table.add_column("Length", style="yellow")

    for topic in topic_set.topics[:5]:
        table.add_row(
            topic.query_id,
            topic.query[:80] + "..." if len(topic.query) > 80 else topic.query,
            str(topic.query_length),
        )

    console.print(table)


@app.command()
def stats(
    file: str = typer.Argument(..., help="Topic file name or path"),
) -> None:
    """Show topic statistics."""
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Resolve file path
    file_path = _resolve_topic_file_path(file, config)

    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    try:
        topic_set = load_topics(file_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error: Topic file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading topics: {e}[/red]")
        raise typer.Exit(1)

    query_lengths = [t.query_length for t in topic_set.topics]

    console.print("[bold]Topic Statistics[/bold]")
    console.print(f"Total topics: {len(topic_set)}")

    if not query_lengths:
        console.print("Query length (avg): N/A")
        console.print("Query length (min): N/A")
        console.print("Query length (max): N/A")
    else:
        console.print(
            f"Query length (avg): {sum(query_lengths) / len(query_lengths):.1f} words"
        )
        console.print(f"Query length (min): {min(query_lengths)} words")
        console.print(f"Query length (max): {max(query_lengths)} words")
