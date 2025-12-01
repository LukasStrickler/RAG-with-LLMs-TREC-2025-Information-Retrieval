#!/usr/bin/env bash

# Helper script to map benchmark arguments to benchmark names
# Usage: benchmark_helper.sh [--23|--24|--dl21|--dl22|--dl23|--msmarco-dev|--msmarco-dev2|--rag23|--rag24]
# Defaults to rag23 if no argument provided

set -euo pipefail

# Default benchmark
BENCHMARK="rag23"

# Parse arguments
if [ $# -gt 0 ]; then
  case "$1" in
    --23|--rag23)
      BENCHMARK="rag23"
      ;;
    --24|--rag24)
      BENCHMARK="rag24"
      ;;
    --dl21)
      BENCHMARK="dl21"
      ;;
    --dl22)
      BENCHMARK="dl22"
      ;;
    --dl23)
      BENCHMARK="dl23"
      ;;
    --msmarco-dev)
      BENCHMARK="msmarco-dev"
      ;;
    --msmarco-dev2)
      BENCHMARK="msmarco-dev2"
      ;;
    *)
      echo "Unknown benchmark argument: $1" >&2
      echo "Available options: --23, --24, --dl21, --dl22, --dl23, --msmarco-dev, --msmarco-dev2" >&2
      exit 1
      ;;
  esac
fi

echo "$BENCHMARK"

