#!/usr/bin/env bash

# Wrapper script to run benchmarks with benchmark selection
# Usage: run_benchmark.sh <mode> [benchmark_arg]
# mode: run-all, lexical, hybrid, vector
# benchmark_arg: --23, --24, --dl21, --dl22, --dl23, --msmarco-dev, --msmarco-dev2

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="$1"
shift || true  # Shift mode, remaining args are benchmark args

# Get benchmark name from helper script
BENCHMARK=$(bash "${PROJECT_ROOT}/scripts/benchmark_helper.sh" "$@")

# Map mode to command
case "$MODE" in
  run-all)
    cd "${PROJECT_ROOT}/backend/eval" && \
    DEV=1 poetry run eval pipeline run-all "$BENCHMARK" --experiment-id benchmark_all_modes
    ;;
  lexical)
    cd "${PROJECT_ROOT}/backend/eval" && \
    DEV=1 poetry run eval pipeline run "$BENCHMARK" --mode lexical --experiment-id benchmark_lexical
    ;;
  hybrid)
    cd "${PROJECT_ROOT}/backend/eval" && \
    DEV=1 poetry run eval pipeline run "$BENCHMARK" --mode hybrid --experiment-id benchmark_hybrid
    ;;
  vector)
    cd "${PROJECT_ROOT}/backend/eval" && \
    DEV=1 poetry run eval pipeline run "$BENCHMARK" --mode vector --experiment-id benchmark_vector
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    echo "Available modes: run-all, lexical, hybrid, vector" >&2
    exit 1
    ;;
esac

