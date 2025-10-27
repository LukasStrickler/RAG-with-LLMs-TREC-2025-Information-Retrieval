"""
Main CLI entrypoint for the evaluation tool.
"""

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
    app()
