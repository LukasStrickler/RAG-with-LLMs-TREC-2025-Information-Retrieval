#!/usr/bin/env bash
# Register Jupyter kernel for Poetry environment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "${SCRIPT_DIR}"

if ! command -v poetry >/dev/null 2>&1; then
    echo "Error: Poetry not found. Please install Poetry first." >&2
    exit 1
fi

echo "Installing dependencies (including ipykernel)..."
poetry install --no-root

echo "Registering Jupyter kernel 'corpus-analysis'..."
poetry run python -m ipykernel install --user --name corpus-analysis --display-name "Python (corpus-analysis)"

echo "✓ Kernel registered successfully!"
echo ""
echo "To use this kernel in Jupyter:"
echo "  1. Open Jupyter: poetry run jupyter notebook"
echo "  2. In the notebook, select Kernel > Jupyter Kernel > Python (corpus-analysis)"

