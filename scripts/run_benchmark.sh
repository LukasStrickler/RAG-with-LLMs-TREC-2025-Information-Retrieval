#!/usr/bin/env bash

# Wrapper script to run benchmarks with benchmark selection
# Usage: run_benchmark.sh <mode> [benchmark_arg]
# mode: run-all, lexical, hybrid, vector
# benchmark_arg: --23, --24, --dl21, --dl22, --dl23, --msmarco-dev, --msmarco-dev2

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="$1"
shift || true  # Shift mode, remaining args are benchmark args and other options

# Separate benchmark selection args from other args (like --limit)
BENCHMARK_ARGS=()
OTHER_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --23|--24|--rag23|--rag24|--dl21|--dl22|--dl23|--msmarco-dev|--msmarco-dev2)
      BENCHMARK_ARGS+=("$arg")
      ;;
    *)
      OTHER_ARGS+=("$arg")
      ;;
  esac
done

# Get benchmark name from helper script
# Handle empty array case for bash with set -u
if [ ${#BENCHMARK_ARGS[@]} -gt 0 ]; then
    BENCHMARK=$(bash "${PROJECT_ROOT}/scripts/benchmark_helper.sh" "${BENCHMARK_ARGS[@]}")
else
    BENCHMARK=$(bash "${PROJECT_ROOT}/scripts/benchmark_helper.sh")
fi

# Get the Poetry venv path
EVAL_DIR="${PROJECT_ROOT}/backend/eval"
VENV_PYTHON="${EVAL_DIR}/.venv/bin/python"

# Map mode to command
# Pass through any additional arguments (e.g., --limit 5) after benchmark selection
case "$MODE" in
  run-all)
    cd "${EVAL_DIR}" && \
    if [ ${#OTHER_ARGS[@]} -gt 0 ]; then
      DEV=1 "${VENV_PYTHON}" -m eval_cli.main pipeline run-all "$BENCHMARK" --experiment-id benchmark_all_modes "${OTHER_ARGS[@]}"
    else
      DEV=1 "${VENV_PYTHON}" -m eval_cli.main pipeline run-all "$BENCHMARK" --experiment-id benchmark_all_modes
    fi
    ;;
  lexical)
    cd "${EVAL_DIR}" && \
    if [ ${#OTHER_ARGS[@]} -gt 0 ]; then
      DEV=1 "${VENV_PYTHON}" -m eval_cli.main pipeline run "$BENCHMARK" --mode lexical --experiment-id benchmark_lexical "${OTHER_ARGS[@]}"
    else
      DEV=1 "${VENV_PYTHON}" -m eval_cli.main pipeline run "$BENCHMARK" --mode lexical --experiment-id benchmark_lexical
    fi
    ;;
  hybrid)
    cd "${EVAL_DIR}" && \
    if [ ${#OTHER_ARGS[@]} -gt 0 ]; then
      DEV=1 "${VENV_PYTHON}" -m eval_cli.main pipeline run "$BENCHMARK" --mode hybrid --experiment-id benchmark_hybrid "${OTHER_ARGS[@]}"
    else
      DEV=1 "${VENV_PYTHON}" -m eval_cli.main pipeline run "$BENCHMARK" --mode hybrid --experiment-id benchmark_hybrid
    fi
    ;;
  vector)
    cd "${EVAL_DIR}" && \
    if [ ${#OTHER_ARGS[@]} -gt 0 ]; then
      DEV=1 "${VENV_PYTHON}" -m eval_cli.main pipeline run "$BENCHMARK" --mode vector --experiment-id benchmark_vector "${OTHER_ARGS[@]}"
    else
      DEV=1 "${VENV_PYTHON}" -m eval_cli.main pipeline run "$BENCHMARK" --mode vector --experiment-id benchmark_vector
    fi
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    echo "Available modes: run-all, lexical, hybrid, vector" >&2
    exit 1
    ;;
esac

