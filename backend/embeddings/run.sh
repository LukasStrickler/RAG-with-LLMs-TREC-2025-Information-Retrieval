#!/bin/bash

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure python3-venv is installed
if ! dpkg -s python3-venv > /dev/null 2>&1; then
    echo "📦 Installing python3-venv..."
    sudo apt-get update && sudo apt-get install -y python3-venv
fi

# Remove broken venv if it exists but is incomplete
if [ -d "venv" ] && [ ! -f "venv/bin/pip" ]; then
    echo "🗑️ Removing broken venv..."
    rm -rf venv
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Use venv's pip and python directly (no activate needed)
VENV_PIP="$SCRIPT_DIR/venv/bin/pip"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"

# Install/upgrade requirements
echo "📥 Installing requirements..."
"$VENV_PIP" install --upgrade pip
"$VENV_PIP" install -r requirements.txt

# Run the ingestion script
echo "🚀 Starting embedding ingestion..."
"$VENV_PYTHON" embedding_ingestion_openrouter.py
