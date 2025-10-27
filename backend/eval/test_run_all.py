#!/usr/bin/env python3
"""
Test script to run evaluation pipeline for all modes.
"""
import sys
from pathlib import Path

from rich.console import Console

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent))

from eval_cli.commands.pipeline import run_all_modes  # noqa: E402

console = Console()


def main():
    """Run evaluation for all modes."""
    console.print(
        "[bold cyan]Starting evaluation pipeline for all modes...[/bold cyan]"
    )

    try:
        # Run the pipeline for all modes
        run_all_modes("rag24")
        console.print("[bold green]✓ Evaluation completed successfully![/bold green]")

    except Exception as e:
        console.print(f"[bold red]✗ Error: {e}[/bold red]")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
