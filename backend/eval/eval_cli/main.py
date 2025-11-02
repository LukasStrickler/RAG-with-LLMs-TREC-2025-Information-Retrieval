"""
Main CLI entrypoint for the TREC RAG Evaluation tool.

This CLI provides comprehensive evaluation workflows for TREC RAG 2025 Information Retrieval track.
It supports loading topics, generating retrieval responses, building TREC runs, computing metrics,
analyzing KPIs, and comparing experiments.

Available subcommands:
- topics: Manage topic files (list, load, stats)
- generate: Generate retrieval responses via API
- runs: Build and validate TREC run files
- score: Score TREC runs and compare results
- benchmark: Compare runs against organizer baselines
- pipeline: End-to-end evaluation pipelines

Example usage:
    # Run complete evaluation pipeline
    poetry run eval pipeline run rag24 --mode hybrid

    # List available topics
    poetry run eval topics list

    # Score a run file
    poetry run eval score run my_run.tsv

    # Compare two runs
    poetry run eval score compare run1.tsv run2.tsv

For detailed documentation, see backend/eval/README.md
"""

import logging
import sys

import typer
from rich.console import Console

# Import command modules
from eval_cli.commands import benchmark, generate, pipeline, runs, score, topics

app = typer.Typer(
    name="eval",
    help="TREC RAG Evaluation CLI",
    add_completion=False,
)
console = Console()

app.add_typer(topics.app, name="topics")
app.add_typer(generate.app, name="generate")
app.add_typer(runs.app, name="runs")
app.add_typer(score.app, name="score")
app.add_typer(benchmark.app, name="benchmark")
app.add_typer(pipeline.app, name="pipeline")

if __name__ == "__main__":
    # Configure logging (after imports, before any logging occurs)
    # This allows users to override logging configuration before importing this module
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        app()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("Unhandled exception in CLI")
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)
