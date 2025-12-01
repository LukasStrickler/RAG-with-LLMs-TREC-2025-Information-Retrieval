#!/usr/bin/env bash

# Download public evaluation assets for the TREC RAG track.
# Assets include:
#   • All TREC RAG/DL qrels and topics (2021-2024)
#   • MS MARCO Dev/Dev2 qrels and topics
#   • 2025 retrieval baselines (top-100 run + reranker request JSONL)
# References:
#   https://trec-rag.github.io/annoucements/2025-rag25-corpus/
#   https://github.com/castorini/ragnarok_data/tree/main/rag25/retrieve_results/MISC

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${PROJECT_ROOT}/.data/trec_rag_assets"

ASSETS=(
  # Qrels files
  "qrels.rag24.test-umbrela-all.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/qrels.rag24.test-umbrela-all.txt"
  "qrels.dl21-doc-msmarco-v2.1.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/qrels.dl21-doc-msmarco-v2.1.txt"
  "qrels.dl22-doc-msmarco-v2.1.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/qrels.dl22-doc-msmarco-v2.1.txt"
  "qrels.dl23-doc-msmarco-v2.1.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/qrels.dl23-doc-msmarco-v2.1.txt"
  "qrels.msmarco-v2.1-doc.dev.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/qrels.msmarco-v2.1-doc.dev.txt"
  "qrels.msmarco-v2.1-doc.dev2.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/qrels.msmarco-v2.1-doc.dev2.txt"
  # Topics files
  "topics.rag24.test.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/topics.rag24.test.txt"
  "topics.dl21.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/topics.dl21.txt"
  "topics.dl22.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/topics.dl22.txt"
  "topics.dl23.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/topics.dl23.txt"
  "topics.msmarco-v2-doc.dev.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/topics.msmarco-v2-doc.dev.txt"
  "topics.msmarco-v2-doc.dev2.txt|https://raw.githubusercontent.com/castorini/anserini-tools/master/topics-and-qrels/topics.msmarco-v2-doc.dev2.txt"
  # 2025 files
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

Includes all TREC RAG/DL qrels and topics (2021-2024), MS MARCO Dev/Dev2,
and 2025 topics plus RankQwen baseline retrieval files.

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
  local tmp_file

  if [[ -f "${target}" && "${FORCE}" -ne 1 ]]; then
    echo "✓ ${label} already present at ${target}"
    return
  fi

  echo "→ Fetching ${label}..."
  tmp_file="$(mktemp)"
  
  # Setup cleanup trap to remove temp file on exit/failure
  trap "rm -f \"${tmp_file}\"" EXIT ERR INT TERM
  
  # Download with error handling
  if ! curl -fL --header "Accept: application/octet-stream" "${url}" -o "${tmp_file}" 2>&1; then
    echo "✗ Error: Failed to download ${label} from ${url}" >&2
    rm -f "${tmp_file}"
    trap "rm -f \"${tmp_file}\"" EXIT ERR INT TERM
    return 1
  fi
  
  # Move temp file to target
  if ! mv "${tmp_file}" "${target}"; then
    echo "✗ Error: Failed to move ${label} to ${target}" >&2
    rm -f "${tmp_file}"
    trap "rm -f \"${tmp_file}\"" EXIT ERR INT TERM
    return 1
  fi
  
  # Clear trap on success
  trap "rm -f \"${tmp_file}\"" EXIT ERR INT TERM
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
echo "Available benchmarks: rag24, dl21, dl22, dl23, msmarco-dev, msmarco-dev2"
echo "Note: Official 2025 qrels have not yet been published; update this script once they are available."
