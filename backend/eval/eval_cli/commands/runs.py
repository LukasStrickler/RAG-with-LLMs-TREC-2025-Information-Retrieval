"""
TREC run management commands.
"""

import json
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from shared.retrieval.response import QueryResult

from eval_cli.config import Config
from eval_cli.io.runs import build_trec_run, read_trec_run, write_trec_run
from eval_cli.models.runs import RunMetadata

app = typer.Typer(help="TREC run management commands")
console = Console()


@app.command()
def build(
    responses: Path = typer.Argument(..., help="JSON file with retrieval responses"),
    output: Path = typer.Option(None, help="Output TREC run file"),
    run_id: str = typer.Option(None, help="Run ID (auto-generated if not provided)"),
) -> None:
    """Build TREC run from retrieval responses."""
    try:
        config = Config.load()
    except FileNotFoundError as e:
        console.print(f"[red]Error: Configuration file not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Load responses
    try:
        with open(responses, encoding="utf-8") as f:
            responses_data = json.load(f)
    except FileNotFoundError as e:
        console.print(f"[red]Error: Responses file not found: {e}[/red]")
        raise typer.Exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON in responses file: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error reading responses file: {e}[/red]")
        raise typer.Exit(1)

    # Convert to QueryResult objects
    try:
        retrieval_responses = {}
        for qid, resp_data in responses_data.items():
            try:
                retrieval_responses[qid] = QueryResult(**resp_data)
            except (TypeError, ValueError) as e:
                console.print(
                    f"[red]Error: Invalid response data for query {qid}: {e}[/red]"
                )
                raise typer.Exit(1)
    except typer.Exit:
        # Re-raise typer.Exit to preserve per-query error messages
        raise
    except Exception as e:
        console.print(f"[red]Error constructing QueryResult objects: {e}[/red]")
        raise typer.Exit(1)

    # Generate run ID if not provided
    if run_id is None:
        run_id = f"mock_run_{responses.stem}"

    # Create metadata
    metadata = RunMetadata(
        run_id=run_id,
        config_snapshot=config.model_dump(),
        topic_source=str(responses),
        retrieval_mode="mock",
        top_k=100,
        num_queries=len(retrieval_responses),
    )

    # Build TREC run
    trec_run = build_trec_run(retrieval_responses, run_id, metadata)

    # Validate format
    errors = trec_run.validate_format()
    if errors:
        console.print("[red]Validation errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)

    # Write run file
    if output is None:
        output = config.get_output_path(f"runs/{run_id}.tsv")

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        console.print(
            f"[red]Error: Cannot create output directory {output.parent}: {e}[/red]"
        )
        raise typer.Exit(1)

    try:
        write_trec_run(trec_run, output)
    except OSError as e:
        console.print(f"[red]Error: Cannot write TREC run file {output}: {e}[/red]")
        console.print(
            "[yellow]Possible causes: permission denied, disk full, or invalid path[/yellow]"
        )
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error writing TREC run file {output}: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓ Built TREC run: {output}[/green]")
    console.print(f"Queries: {metadata.num_queries}")
    console.print(f"Total results: {len(trec_run.rows)}")


@app.command()
def validate(
    run_file: Path = typer.Argument(..., help="TREC run file to validate"),
) -> None:
    """Validate TREC run format."""
    try:
        trec_run = read_trec_run(run_file)
    except FileNotFoundError:
        console.print(f"[red]Error: Run file not found: {run_file}[/red]")
        console.print("[yellow]Please check the file path and try again[/yellow]")
        raise typer.Exit(1)
    except PermissionError:
        console.print(
            f"[red]Error: Permission denied reading run file {run_file}[/red]"
        )
        console.print("[yellow]Please check file permissions and try again[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error reading or parsing run file {run_file}: {e}[/red]")
        console.print(
            "[yellow]Please verify the file is a valid TREC run file[/yellow]"
        )
        raise typer.Exit(1)

    errors = trec_run.validate_format()

    if not errors:
        console.print("[green]✓ TREC run format is valid[/green]")
    else:
        console.print("[red]✗ TREC run format errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)


@app.command()
def info(
    run_file: Path = typer.Argument(..., help="TREC run file"),
) -> None:
    """Show TREC run information."""
    try:
        trec_run = read_trec_run(run_file)
    except FileNotFoundError as e:
        console.print(f"[red]Error: Run file not found: {e}[/red]")
        raise typer.Exit(1)
    except PermissionError as e:
        console.print(
            f"[red]Error: Permission denied reading run file {run_file}: {e}[/red]"
        )
        raise typer.Exit(1)
    except OSError as e:
        console.print(f"[red]Error: OS error reading run file {run_file}: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error reading run file {run_file}: {e}[/red]")
        raise typer.Exit(1)

    try:
        # Count queries and documents using Counter
        query_counts = Counter(row.query_id for row in trec_run.rows)

        table = Table(title="TREC Run Information")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Run ID", trec_run.metadata.run_id)
        table.add_row("Total Queries", str(len(query_counts)) if query_counts else "0")
        table.add_row("Total Results", str(len(trec_run.rows)))

        if query_counts:
            table.add_row(
                "Avg Results/Query", f"{len(trec_run.rows) / len(query_counts):.1f}"
            )
            table.add_row("Max Results/Query", str(max(query_counts.values())))
            table.add_row("Min Results/Query", str(min(query_counts.values())))
        else:
            table.add_row("Avg Results/Query", "0.0")
            table.add_row("Max Results/Query", "0")
            table.add_row("Min Results/Query", "0")

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error processing run data: {e}[/red]")
        raise typer.Exit(1)
