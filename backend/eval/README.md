# Evaluation CLI

Comprehensive evaluation CLI for TREC RAG 2025 Information Retrieval track.

## Overview

The evaluation CLI provides a complete workflow for:
- Loading topic files (TREC and JSONL formats)
- Generating retrieval responses via API
- Building TREC-compliant run files
- Computing evaluation metrics (nDCG, MAP, MRR, Recall, HitRate)
- Tracking KPIs against targets
- Comparing retrieval modes (lexical, vector, hybrid)
- Benchmarking against organizer baselines

## Quick Start

### 1. Prerequisites

```bash
# Install dependencies
cd backend/eval
poetry install

# Ensure API server is running (required for retrieval)
npm run backend:dev  # In project root

# Ensure data files are available
# Topic files and qrels should be in .data/trec_rag_assets/
```

### 2. Basic Usage

#### Option A: Using npm scripts (Recommended)

```bash
# From project root - handles Poetry environment automatically
# Default benchmark: rag23 (TREC DL 2023)

# Run all retrieval modes (lexical, vector, hybrid)
npm run benchmark                    # Uses rag23 (default)
npm run benchmark -- --24           # Override: use rag24
npm run benchmark -- --dl21         # Override: use dl21
npm run benchmark -- --msmarco-dev  # Override: use msmarco-dev

# Run specific retrieval mode
npm run benchmark:lexical            # Lexical mode, rag23 (default)
npm run benchmark:lexical -- --24   # Lexical mode, rag24
npm run benchmark:lexical -- --limit 5  # Lexical mode with 5 queries only

npm run benchmark:hybrid            # Hybrid mode, rag23 (default)
npm run benchmark:hybrid -- --24     # Hybrid mode, rag24
npm run benchmark:hybrid -- --limit 5  # Hybrid mode with 5 queries only

npm run benchmark:vector            # Vector mode, rag23 (default)
npm run benchmark:vector -- --24     # Vector mode, rag24
npm run benchmark:vector -- --limit 5  # Vector mode with 5 queries only

# Available benchmark flags:
# --23, --rag23    → TREC DL 2023 (default)
# --24, --rag24    → TREC RAG 2024
# --dl21           → TREC DL 2021
# --dl22           → TREC DL 2022
# --dl23           → TREC DL 2023
# --msmarco-dev    → MS MARCO Dev
# --msmarco-dev2   → MS MARCO Dev2
```

#### Option B: Using poetry directly

```bash
# Run evaluation for a single mode
poetry run eval pipeline run rag23 --mode hybrid
poetry run eval pipeline run rag23 --mode lexical --limit 5  # Limit to 5 queries

# Run evaluation for all modes and compare
poetry run eval pipeline run-all rag23 --experiment-id baseline_v1
poetry run eval pipeline run-all rag23 --limit 5  # Limit to 5 queries for all modes

# List previous experiments
poetry run eval pipeline list

# Compare two experiments
poetry run eval pipeline compare experiment1 experiment2
```

**Query Limiting:** Use `--limit N` to process only the first N queries and filter qrels accordingly. Useful for quick testing.

## Architecture

### Directory Structure

```text
backend/eval/
├── eval_cli/                    # CLI implementation
│   ├── main.py                 # CLI entrypoint
│   ├── config.py               # Configuration management
│   ├── client.py                # API client
│   ├── commands/                # CLI commands
│   │   ├── topics.py           # Topic loading commands
│   │   ├── generate.py         # Response generation
│   │   ├── runs.py             # Run building/validation
│   │   ├── score.py            # Scoring and KPI analysis
│   │   ├── benchmark.py        # Baseline comparison
│   │   └── pipeline.py         # End-to-end workflows
│   ├── io/                     # I/O utilities
│   │   ├── topics.py           # Topic file loading
│   │   ├── qrels.py            # Qrels loading
│   │   └── runs.py             # TREC run I/O
│   ├── models/                 # Data models
│   │   ├── topics.py           # Topic/TopicSet
│   │   ├── runs.py             # TrecRunRow/TrecRun
│   │   ├── reports.py          # EvaluationReport
│   │   └── baselines.py        # Baseline comparison
│   ├── scoring/                # Evaluation logic
│   │   ├── trec_eval.py        # trec_eval wrapper
│   │   ├── custom_metrics.py   # HitRate@10, etc.
│   │   └── kpi_analyzer.py     # KPI target analysis
│   └── mock/                   # Mock data utilities
│       └── baseline_loader.py  # Baseline run loading
├── config.yaml                 # Configuration file
├── .env                        # API credentials (API_BASE_URL, API_KEY)
├── .env.example                # Template for .env
└── artifacts/                  # Output directory
    ├── experiments/            # Timestamped experiments
    ├── runs/                   # Individual run files
    └── reports/                # KPI reports
```

## Configuration

### Environment Variables (.env)

API credentials and settings are loaded from `backend/eval/.env`:

```bash
# API Configuration
API_BASE_URL=http://localhost:8000
API_KEY=dev-api-key-for-testing-purposes-only-32chars

# API Request Configuration
API_TIMEOUT=30
API_MAX_RETRIES=3
API_CONCURRENCY=5
```

**Important:** Copy `.env.example` to `.env` and update with your API credentials.

### Configuration File (config.yaml)

Main configuration for paths, metrics, and targets:

```yaml
api:
  timeout: 30
  max_retries: 3
  concurrency: 5

retrieval:
  modes: [lexical, vector, hybrid]
  default_mode: hybrid
  top_k: 100

paths:
  project_root: null  # Auto-detected
  data_dir: ".data/trec_rag_assets"
  output_dir: "backend/eval/artifacts"
  topics:
    rag23: "topics.dl23.txt"  # Default: TREC DL 2023
    rag24: "topics.rag24.test.txt"
    dl21: "topics.dl21.txt"
    dl22: "topics.dl22.txt"
    dl23: "topics.dl23.txt"
    msmarco-dev: "topics.msmarco-v2-doc.dev.txt"
    msmarco-dev2: "topics.msmarco-v2-doc.dev2.txt"
    rag25: "trec_rag_2025_queries.jsonl"
  qrels:
    rag23: "qrels.dl23-doc-msmarco-v2.1.txt"  # Default: TREC DL 2023
    rag24: "qrels.rag24.test-umbrela-all.txt"
    dl21: "qrels.dl21-doc-msmarco-v2.1.txt"
    dl22: "qrels.dl22-doc-msmarco-v2.1.txt"
    dl23: "qrels.dl23-doc-msmarco-v2.1.txt"
    msmarco-dev: "qrels.msmarco-v2.1-doc.dev.txt"
    msmarco-dev2: "qrels.msmarco-v2.1-doc.dev2.txt"
    rag25: null  # Organizer qrels pending
  baselines:
    rag24: "fs4_bm25+rocchio_snowael_snowaem_gtel+monot5_rrf+rz_rrf.rag24.test.txt"
    rag25: "run.rankqwen3_32b.rag25.txt"

metrics:
  primary: "ndcg_cut_10"
  targets:
    ndcg_cut_10: 0.30
    ndcg_cut_25: 0.32
    ndcg_cut_50: 0.30
    ndcg_cut_100: 0.28
    map_cut_100: 0.25
    recip_rank: 0.45
    recall_25: 0.55
    recall_50: 0.60
    recall_100: 0.62
    hitrate_10: 0.70
```

## Commands

### Topics

Load and inspect topic files:

```bash
# List available topic files
poetry run eval topics list

# Load and display a topic file (shows first 5 topics)
poetry run eval topics load rag23

# Show statistics
poetry run eval topics stats rag23
```

### Generate Responses

Generate retrieval responses via API:

```bash
# Generate responses for all topics
poetry run eval generate run rag23

# Specify output file and top_k
poetry run eval generate run rag23 --output results.json --top-k 100
```

### Runs

Build and validate TREC run files:

```bash
# Build TREC run from responses
poetry run eval runs build responses.json --run-id my_run

# Validate TREC run format
poetry run eval runs validate my_run.tsv

# Show run information
poetry run eval runs info my_run.tsv
```

### Scoring

Compute metrics and KPI analysis:

```bash
# Score a run file
poetry run eval score run my_run.tsv

# Compare two runs
poetry run eval score compare run1.tsv run2.tsv
```

### Benchmarking

Compare against organizer baselines:

```bash
# Compare your run against baseline
poetry run eval benchmark compare my_run.tsv --year rag23

# Show baseline targets
poetry run eval benchmark targets
```

### Pipeline (End-to-End)

Complete evaluation workflows:

**Using npm scripts (from project root):**
```bash
# Run all modes and compare (recommended)
npm run benchmark                    # Default: rag23
npm run benchmark -- --24            # Override: rag24
npm run benchmark -- --dl21          # Override: dl21

# Run specific retrieval mode
npm run benchmark:lexical            # Lexical (BM25), rag23 (default)
npm run benchmark:lexical -- --24    # Lexical (BM25), rag24
npm run benchmark:hybrid             # Hybrid (fusion), rag23 (default)
npm run benchmark:hybrid -- --24     # Hybrid (fusion), rag24
npm run benchmark:vector             # Vector (semantic), rag23 (default)
npm run benchmark:vector -- --24     # Vector (semantic), rag24
```

**Using poetry directly:**
```bash
# Run single mode evaluation
poetry run eval pipeline run rag23 --mode hybrid --experiment-id test1

# Run all modes and compare
poetry run eval pipeline run-all rag23 --experiment-id baseline_v1

# List previous experiments
poetry run eval pipeline list

# Compare two experiments
poetry run eval pipeline compare experiment1 experiment2
```

## Available Benchmarks

The CLI supports multiple TREC benchmarks. Use the `--` flag with npm scripts to override the default (rag23):

| Flag | Benchmark | Description | Topics |
|------|-----------|-------------|--------|
| `--23`, `--rag23` | TREC DL 2023 | Default benchmark | 700 |
| `--24`, `--rag24` | TREC RAG 2024 | UMBRELA test set | 301 |
| `--dl21` | TREC DL 2021 | Deep Learning 2021 | 477 |
| `--dl22` | TREC DL 2022 | Deep Learning 2022 | 500 |
| `--dl23` | TREC DL 2023 | Deep Learning 2023 | 700 |
| `--msmarco-dev` | MS MARCO Dev | Development set | 4,552 |
| `--msmarco-dev2` | MS MARCO Dev2 | Development set 2 | 5,000 |

**Example:**
```bash
# Use default (rag23)
npm run benchmark:lexical

# Override to rag24
npm run benchmark:lexical -- --24

# Override to dl21
npm run benchmark:lexical -- --dl21
```

## Retrieval Modes

The CLI supports three retrieval modes:

1. **Lexical** - BM25-based term matching
2. **Vector** - Semantic embeddings
3. **Hybrid** - Fusion of lexical + vector

Set the mode via:
- CLI argument: `--mode hybrid`
- Config file: `retrieval.default_mode`
- Environment variable: `API_MODE` (future)

## KPI Tracking

The CLI computes and tracks KPIs against targets defined in `config.yaml`. 

**Note:** The targets in `config.yaml` represent baseline performance levels (e.g., BM25 baseline). For competitive targets (higher performance goals), see `.docs/KPI.md` which documents:
- **Competitive targets**: nDCG@10 ≥0.35, MAP@100 ≥0.28, MRR@10 ≥0.55
- **Baseline targets** (in config.yaml): nDCG@10 ≥0.30, MAP@100 ≥0.25, MRR@10 ≥0.45

### Primary KPIs

- **nDCG@10** - Primary leaderboard metric (baseline target: 0.30)
- **MAP@100** - Comprehensive ranking quality (baseline target: 0.25)
- **MRR@10** - First relevant hit latency (baseline target: 0.45)

### Secondary KPIs

- **Recall@K** - Coverage at 25, 50, 100
- **HitRate@10** - Binary success rate (baseline target: 0.70)

### KPI Reports

Each experiment generates KPI reports showing:

```json
{
  "metrics": [
    {
      "name": "nDCG@10",
      "value": 0.342,
      "target": 0.30,
      "status": "pass",
      "higher_is_better": true
    },
    ...
  ],
  "status_counts": {
    "pass": 3,
    "fail": 5,
    "warn": 2,
    "unknown": 1
  },
  "overall_status": "warn"
}
```

## Output Structure

Experiments are organized with timestamps for easy comparison:

```text
artifacts/
└── experiments/
    └── baseline_v1_rag23_20251024_183800/
        ├── lexical/
        │   ├── baseline_v1_rag23_20251024_183800_lexical.tsv
        │   └── baseline_v1_rag23_20251024_183800_lexical_report.json
        ├── vector/
        │   ├── baseline_v1_rag23_20251024_183800_vector.tsv
        │   └── baseline_v1_rag23_20251024_183800_vector_report.json
        └── hybrid/
            ├── baseline_v1_rag23_20251024_183800_hybrid.tsv
            └── baseline_v1_rag23_20251024_183800_hybrid_report.json
```

## Integration with API

**Note:** The API currently returns mock responses for development and testing. Real retrieval services will be integrated in future updates.

The CLI communicates with the retrieval API server:

```text
┌─────────────┐         ┌──────────────┐
│  Eval CLI   │────────▶│  API Server  │
│             │ Request │              │
│             │◀────────│  Response    │
└─────────────┘         └──────────────┘
```

**Request Format:**
```json
{
  "mode": "hybrid",
  "queries": [
    {
      "query_id": "2000138",
      "query_text": "What is machine learning?",
      "top_k": 100
    }
  ]
}
```

**Response Format:**
```json
{
  "schema_version": "1.0",
  "dataset_version": "trec_rag_2023",
  "config_hash": "hybrid_config_v1",
  "request_id": "uuid-here",
  "results": [
    {
      "query_id": "2000138",
      "segments": [
        {
          "segment_id": "...",
          "score": 0.95,
          "metadata": {...},
          "provenance": {...}
        }
      ],
      "diagnostics": {
        "latency_ms": 123.45,
        "config_hash": "...",
        "index_versions": {},
        "warnings": []
      }
    }
  ]
}
```

The endpoint is `/api/v1/retrieve` and requires authentication via `X-API-Key` header.

## Error Handling

The CLI provides comprehensive error handling with clear, actionable messages for:
- **API errors**: Connection failures, timeouts, and authentication issues
- **Configuration errors**: Missing config files or invalid settings
- **File I/O errors**: Missing files, permission issues, and invalid paths
- **Validation errors**: TREC format violations with specific query IDs and issues

All errors are logged with context and exit with appropriate status codes for CI/CD integration.

## Development

### Running Tests

```bash
poetry run pytest tests/
```

### Project Structure

The CLI is organized into modular components:

- **commands/** - CLI command implementations
- **io/** - Data loading and file operations
- **models/** - Pydantic data models
- **scoring/** - Evaluation and KPI logic
- **client.py** - API client with error handling
- **config.py** - Configuration management

### Adding New Commands

Commands are implemented as Typer apps in `eval_cli/commands/`:

```python
import typer
from rich.console import Console

app = typer.Typer(help="My command help")
console = Console()

@app.command()
def my_command(arg: str = typer.Argument(...)):
    """My command description."""
    console.print(f"Running: {arg}")
```

## Troubleshooting

### API Authentication Errors

- Check `API_KEY` in `backend/eval/.env` matches `backend/api/.env`
- **Note**: API keys are now stored as `SecretStr` for security - they won't appear in logs
- Ensure API server is running: `npm run backend:dev`

### Missing Data Files

- Topic files and qrels should be in `.data/trec_rag_assets/`
- Download using: `npm run pull:qrel`
- The download script fetches all available benchmarks:
  - TREC RAG 2024 (rag24)
  - TREC DL 2021-2023 (dl21, dl22, dl23)
  - MS MARCO Dev/Dev2 (msmarco-dev, msmarco-dev2)

### Configuration Issues

- Ensure `config.yaml` exists in `backend/eval/`
- Check `.env` file has correct values
- Verify `API_BASE_URL` points to running server

## References

- [TREC RAG 2025](https://trec-rag.github.io/)
- [KPI.md](../../.docs/KPI.md) - KPI definitions and targets
