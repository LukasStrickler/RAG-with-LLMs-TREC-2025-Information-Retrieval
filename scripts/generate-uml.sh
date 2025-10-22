#!/bin/bash
#
# Generate UML diagrams from shared Pydantic models
#
# Prerequisites:
#   - Poetry (>=1.7.0)
#   - Python (>=3.10)
#   - shared/ package with Poetry environment
#
# Usage:
#   ./scripts/generate-uml.sh
#   # or via npm: npm run docs:uml
#
# Output:
#   .docs/uml/generated_classes.puml
#
# Environment:
#   PYTHONPATH is set automatically to resolve shared package imports
#
# Troubleshooting:
#   - If poetry not found: install via https://python-poetry.org/docs/#installation
#   - If imports fail: ensure `cd shared && poetry install` was run
#   - If output empty: check scripts/generate_uml.py for errors

set -e
set -o pipefail

# Validate required tools
command -v poetry >/dev/null 2>&1 || { echo "Error: poetry not found" >&2; exit 1; }

echo "Generating UML diagrams from shared types..."

# Determine project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Validate required directories and files
[ -d "$PROJECT_ROOT/shared" ] || { echo "Error: shared/ directory not found" >&2; exit 1; }
[ -f "$PROJECT_ROOT/scripts/generate_uml.py" ] || { echo "Error: generate_uml.py not found" >&2; exit 1; }

cd "$PROJECT_ROOT"

# Ensure shared Poetry environment is set up
echo "Setting up shared Poetry environment..."
cd shared
poetry install --no-root
cd ..

# Generate UML for shared types using our custom generator
echo "Generating UML for shared types..."
cd shared
temp_file=$(mktemp)
if ! poetry run python ../scripts/generate_uml.py > "$temp_file" 2>&1; then
    echo "Error: UML generation failed" >&2
    cat "$temp_file" >&2
    rm -f "$temp_file"
    exit 1
fi

# Validate output is not empty
if [ ! -s "$temp_file" ]; then
    echo "Error: Generated UML file is empty" >&2
    rm -f "$temp_file"
    exit 1
fi

mv "$temp_file" shared_types.puml
cd ..

# Create .docs/uml directory if it doesn't exist
mkdir -p .docs/uml

# Move generated file to .docs directory
mv shared/shared_types.puml .docs/uml/generated_classes.puml

echo "UML generation complete!"
echo "Generated file: .docs/uml/generated_classes.puml"
echo "Compare with: .docs/uml/classes.puml"
