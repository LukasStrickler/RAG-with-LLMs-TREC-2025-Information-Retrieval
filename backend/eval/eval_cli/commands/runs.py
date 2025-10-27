"""
TREC run management commands.
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

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
    config = Config.load()

    # Load responses
    with open(responses) as f:
        responses_data = json.load(f)

    # Convert to QueryResult objects
    from shared.retrieval.response import QueryResult

    retrieval_responses = {
        qid: QueryResult(**resp_data) for qid, resp_data in responses_data.items()
    }

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

    output.parent.mkdir(parents=True, exist_ok=True)
    write_trec_run(trec_run, output)

    console.print(f"[green]✓ Built TREC run: {output}[/green]")
    console.print(f"Queries: {metadata.num_queries}")
    console.print(f"Total results: {len(trec_run.rows)}")


@app.command()
def validate(
    run_file: Path = typer.Argument(..., help="TREC run file to validate"),
) -> None:
    """Validate TREC run format."""
    trec_run = read_trec_run(run_file)

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
    trec_run = read_trec_run(run_file)

    # Count queries and documents
    query_counts = {}
    for row in trec_run.rows:
        query_counts[row.query_id] = query_counts.get(row.query_id, 0) + 1

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
