#!/usr/bin/env bash

# Download public evaluation assets for the TREC RAG track.
# Assets include:
#   • 2024 UMBRELA qrels/topics (most recent public relevance labels)
#   • 2025 retrieval baselines (top-100 run + reranker request JSONL)
# References:
#   https://trec-rag.github.io/annoucements/umbrela-qrels/
#   https://github.com/castorini/ragnarok_data/tree/main/rag25/retrieve_results/MISC

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${PROJECT_ROOT}/.data/trec_rag_assets"

ASSETS=(
  "qrels.rag24.test-umbrela-all.txt|https://trec-rag.github.io/assets/txt/qrels.rag24.test-umbrela-all.txt"
  "topics.rag24.test.txt|https://trec-rag.github.io/assets/txt/topics.rag24.test.txt"
  "fs4_bm25+rocchio_snowael_snowaem_gtel+monot5_rrf+rz_rrf.rag24.test.txt|https://raw.githubusercontent.com/castorini/ragnarok_data/main/rag24/retrieve_results/RANK_ZEPHYR/fs4_bm25+rocchio_snowael_snowaem_gtel+monot5_rrf+rz_rrf.rag24.test.txt"
  "retrieve_results_fs4_bm25+rocchio_snowael_snowaem_gtel+monot5_rrf+rz_rrf.rag24.test_top100.jsonl|https://raw.githubusercontent.com/castorini/ragnarok_data/main/rag24/retrieve_results/RANK_ZEPHYR/retrieve_results_fs4_bm25+rocchio_snowael_snowaem_gtel+monot5_rrf+rz_rrf.rag24.test_top100.jsonl"
  "trec_rag_2025_queries.jsonl|https://trec-rag.github.io/assets/jsonl/trec_rag_2025_queries.jsonl"
  "run.rankqwen3_32b.rag25.txt|https://raw.githubusercontent.com/castorini/ragnarok_data/main/rag25/retrieve_results/MISC/run.rankqwen3_32b.rag25.txt"
  "retrieve_results_rankqwen3_32b.rag25_top100.jsonl|https://media.githubusercontent.com/media/castorini/ragnarok_data/main/rag25/retrieve_results/MISC/retrieve_results_rankqwen3_32b.rag25_top100.jsonl"
)

FORCE=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [--force]

Downloads the latest publicly released TREC RAG assets into:
  ${DATA_DIR}

Includes 2024 UMBRELA qrels/topics + baseline run, and 2025 topics plus RankQwen baseline retrieval files.

Pass --force to overwrite existing files.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

mkdir -p "${DATA_DIR}"

download_file() {
  local url="$1"
  local target="$2"
  local label="$3"

  if [[ -f "${target}" && "${FORCE}" -ne 1 ]]; then
    echo "✓ ${label} already present at ${target}"
    return
  fi

  echo "→ Fetching ${label}..."
  tmp_file="$(mktemp)"
  curl -fL --header "Accept: application/octet-stream" "${url}" -o "${tmp_file}"
  mv "${tmp_file}" "${target}"
  echo "✓ Saved ${label} to ${target}"
}

for entry in "${ASSETS[@]}"; do
  filename="${entry%%|*}"
  url="${entry#*|}"
  target="${DATA_DIR}/${filename}"
  download_file "${url}" "${target}" "${filename}"
done

echo ""
echo "Stored competition evaluation assets under ${DATA_DIR}."
echo "Note: Official 2025 qrels have not yet been published; update this script once they are available."
