#!/usr/bin/env python3
"""
Test script to run evaluation pipeline for all modes.
"""
import argparse
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
    """
    Run evaluation for all modes.
    
    Accepts a command-line argument for the topic set (e.g., rag24, rag25)
    with a default value of 'rag24'.
    """
    parser = argparse.ArgumentParser(
        description="Run evaluation pipeline for all retrieval modes (lexical, vector, hybrid).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s                    # Use default topic set 'rag24'\n"
            "  %(prog)s rag25              # Use topic set 'rag25'\n"
            "  %(prog)s /path/to/topics.xml  # Use custom topic file path"
        ),
    )
    parser.add_argument(
        "topics",
        nargs="?",
        default="rag24",
        help="Topic set identifier (e.g., rag24, rag25) or path to topic file (default: rag24)",
    )

    args = parser.parse_args()

    console.print(
        f"[bold cyan]Starting evaluation pipeline for all modes with topic set: {args.topics}...[/bold cyan]"
    )

    try:
        # Run the pipeline for all modes
        run_all_modes(args.topics)
        console.print("[bold green]✓ Evaluation completed successfully![/bold green]")

    except Exception as e:
        console.print(f"[bold red]✗ Error: {e}[/bold red]")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
