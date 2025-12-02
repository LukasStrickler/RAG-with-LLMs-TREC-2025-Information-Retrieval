# Embeddings & Ingestion Pipeline

This service ingests documents from PostgreSQL into Qdrant and documents the journey we took to make embeddings practical at scale. It covers local GPU pipelines with chunking, A100 experiments, and the final remote embeddings approach via OpenRouter, including trade-offs, costs, and reproducible run guidance.

## Overview

- **Source**: PostgreSQL (`documents` table)
- **Destination**: Qdrant (primary collection name varies; e.g., `small`, `small_openrouter_nc`)
- **Local Model**: `Qwen/Qwen3-Embedding-0.6B` (1024 dims; small context window → chunking required)
- **Remote Model**: `Qwen 3 8B Embedding` via OpenRouter (larger window → no chunking)
- **Runtime Modes**:
    - Local GPU notebook/script (chunk + embed + upsert)
    - Remote embeddings via API (embed via OpenRouter, same ingest/upsert pipeline)

Key implementation files:
- Notebook: `backend/embeddings/embedding_ingestion.ipynb` (SSH tunnel setup, pipelined ingestion, progress metrics, helpers)
- Scripts: `backend/embeddings/ingest.py`, `backend/embeddings/embedding_ingestion_openrouter.py` (local vs remote encoder swap)
- DB adapter: `backend/embeddings/db.py` (threaded connection pool, dataset/doc fetch)
- Qdrant helpers: upsert batching, collection setup embedded in the notebook/script

## Timeline & Trade-offs

We needed to process ~1.6M documents with ~3k tokens per document on average.

- **Local GPU (RTX 5070 Ti) with chunking**
    - Pipeline: SSH tunnels → fetch → chunk (512 + overlap 50) → embed → batched upsert.
    - Result: ~5 docs/sec in practice. VRAM was not the bottleneck; compute (matrix ops + embedding) dominated. Chunking increased total tokens and runtime.
    - Parallelism: Prefetch/Embed/Upsert pipelined; multiple local model instances didn’t materially improve end-to-end throughput.
    - Token math: ~3,000 tokens/doc × 1.6M docs ≈ 4.8B tokens. With chunking (overlap adds repeat tokens), effective tokens grow further, compounding runtime.
    - Batching & precision: BF16 on CUDA to cut memory, hard-clamped `max_seq_length=512` to avoid tokenizer inflating sequence lengths.

- **A100 (80GB) attempt**
    - Tried larger batches and multiple model workers to leverage VRAM and bandwidth.
    - Constraint: Compute stayed the limiter; aggressive batching hit VRAM ceilings. Gains were marginal relative to scale.
    - Observation: Embedding generation saturated compute; VRAM increases did not translate to proportional docs/sec improvements.

- **Remote embeddings via OpenRouter (Final)**
    - Kept the same pipeline; swapped encoder to API calls.
    - Model: `Qwen 3 8B Embedding` with a larger context window → removed chunking.
    - Outcome: Best throughput and scalability; operationally simpler.
    - Cost: ~$0.05 per 1M tokens. With 1.6M docs × ~3k tokens/doc, full coverage was too expensive.
    - Compromise: Fixed-budget run → ~400k embedded docs. Included all qrels-referenced documents to support evaluation.
    - Benefit: Simpler ingestion metadata (no chunk indices), lower latency per doc, fewer Qdrant points per document.
    - Next bottleneck: SSH tunnel bandwidth limited network throughput for pulling docs and upserting points.
    - Final infra change: Run the pipeline directly on our Linux server (close to Postgres/Qdrant). Result: significantly faster document fetches and upserts (lower latency, higher sustained throughput).

## Setup

1. **Prerequisites**
     - Python 3.11+
     - PostgreSQL and Qdrant reachable via SSH tunnel (dev)
     - Optional CUDA-capable GPU for local runs

2. **Install dependencies (pipenv)**
     ```bash
     pipenv install
     ```

3. **SSH tunnels**
     - Postgres: `localhost:5433`
     - Qdrant: `localhost:6333` (HTTP) and/or `localhost:6334` (gRPC)
    - Note: For high-throughput runs, prefer running on the same network/host as Postgres/Qdrant to avoid SSH tunnel bottlenecks.

4. **Environment variables (remote mode)**
    - `OPENROUTER_API_KEY`: API key for OpenRouter
    - `EMBEDDING_MODEL_ID`: e.g., `Qwen/Qwen3-Embedding-0.6B` (local) or OpenRouter’s `qwen-3-8b-embedding`
    - Optional knobs: `BATCH_SIZE`, `QDRANT_UPSERT_BATCH`, `PREFETCH_BATCHES`, `NUM_EMBED_WORKERS`, `RESUME_INGESTION`, `PURGE_COLLECTION`

## Usage

Run the local ingestion pipeline:

```bash
pipenv run python ingest.py
```

Notebook-based ingestion and helpers live in `embedding_ingestion.ipynb`.

Remote embeddings runner (example):

```bash
export OPENROUTER_API_KEY=... 
pipenv run python embedding_ingestion_openrouter.py
```

## Configuration

- **Database**: configured in `ingest.py` (aligned with `backend/search`).
- **Qdrant**: defaults to local tunnel (`6333/6334`).
- **Model**: local mode uses `Qwen/Qwen3-Embedding-0.6B`; remote mode configures OpenRouter.
 - **Chunking**: enabled for small-context models (512 window, 50 overlap); disabled for larger-window remote model.
 - **Resume**: enabled by default to skip already-ingested `doc_id`s.

## Logging & Tracking

- Validates chunking configurations where applicable; progress via `tqdm`.
- Upserts in batches, `wait=False` to avoid indexing stalls.
 - Rolling per-stage throughput (docs/sec) displayed: fetch, embed, upsert.

## Pipeline Walkthrough (Local)

1. **Initialization**: connect to Postgres and Qdrant via SSH; load local embedding model.
2. **Dataset Selection**: select target dataset (e.g., `small`); reuse name as Qdrant collection.
3. **Collection Setup**: create collection with COSINE distance and correct vector size.
4. **Processing Loop**: fetch doc IDs in batches; retrieve doc contents.
5. **Batch Processing**:
     - Chunking (512 window, 50 overlap) for small-context models.
     - Embedding on GPU/CPU; deterministic UUIDs (`uuid5(doc_id + chunk_index)`).
     - Upsert points + payload (doc_id, chunk_index, text, title, url, dataset).
6. **Completion**: progress reported; DB connections closed.

### Local Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Local Pipelined Ingestion (Chunked)                      │
├────────────┬────────────────────┬──────────────────────┬────────────────────┤
│  Prefetch  │    Chunk & Embed   │       Upsert         │      Progress      │
│  (DB I/O)  │   (GPU/CPU compute)│     (Network I/O)    │      Metrics       │
├────────────┼────────────────────┼──────────────────────┼────────────────────┤
│ Thread T0  │  Thread(s) T1..Tk  │     Thread T(k+1)    │  tqdm w/ fetch/embed│
│ PostgreSQL │  SentenceTransformer│      Qdrant client   │  /upsert docs/sec  │
└────────────┴────────────────────┴──────────────────────┴────────────────────┘
Queues: doc_queue (size = PREFETCH × workers), points_queue (same)
```

## Pipeline Walkthrough (Remote/OpenRouter)

1. **Initialization**: same DB/Qdrant wiring; configure OpenRouter API key.
2. **Embedding**: call the remote embedding API; skip chunking thanks to larger context window.
3. **Upsert**: identical Qdrant batching strategy.
4. **Cost Awareness**: run under fixed budget; prioritize qrels-linked docs; add representative subset.

### Remote Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Remote Embeddings (No Chunking)                            │
├────────────┬───────────────────────────┬──────────────────────┬─────────────┤
│  Prefetch  │      Embed via API        │       Upsert         │  Progress   │
│  (DB I/O)  │   (OpenRouter service)    │     (Network I/O)    │  Metrics    │
├────────────┼───────────────────────────┼──────────────────────┼─────────────┤
│ Thread T0  │  Async HTTP requests      │     Thread T2        │  docs/sec   │
│ PostgreSQL │  Larger context window    │     Qdrant client    │  per stage  │
└────────────┴───────────────────────────┴──────────────────────┴─────────────┘
Simplifies payload: one point per document (no chunk indices)
```

## Architecture & Design Notes

- **Chunking rationale**: improves passage-level retrieval for small-context models; removed when using larger-window remote model.
- **Compute vs VRAM**: local runs were compute-bound; VRAM expansions didn’t unlock material throughput.
- **Pipelining**: prefetch/embedding/upsert overlapped to keep GPU/network busy.
- **Resume**: supports resuming from last processed `doc_id` to avoid re-ingest.
 - **Deterministic IDs**: stable UUID generation prevents duplicates on re-runs.
 - **Qdrant indexing**: `OptimizersConfigDiff(indexing_threshold=50000)` can delay heavy indexing during bulk upserts.

## Evaluation Linkage

- We ensured all qrels-referenced docs were embedded and present in the collection.
- Run evaluation via the CLI in `backend/eval`; vector/hybrid modes consume this collection.
 - Helper: notebook cell to fetch and persist `document_ids` from a collection (e.g., `small_openrouter_nc_doc_ids.json`).

## Practical Tips

- Under budget constraints, embed qrels first, then expand.
- Monitor per-stage throughput (fetch/embed/upsert) to identify bottlenecks.
- For notebooks: warm up models; verify tunnels; keep `QDRANT_UPSERT_BATCH` moderate to avoid timeouts.

## Cost Estimation (Remote)

- Pricing example: ~$0.05 per 1M tokens.
- Tokens per doc: assume ~3,000.
- Total tokens: `docs × tokens_per_doc`.
- Cost: `total_tokens / 1e6 × $0.05`.

Examples:
- 100k docs → 300M tokens → $15.
- 400k docs → 1.2B tokens → $60.
- 1.6M docs → 4.8B tokens → $240. Overlaps, headers, and serialization overhead can add marginally to token counts.

Practical budgeting:
- Run qrels set first; pre-calculate token budget for a candidate subset.
- Prefer larger context window models to avoid chunking (reduces total tokens processed).

## Configuration Reference (Key Knobs)

- `BATCH_SIZE`: docs per batch for prefetch/embedding.
- `QDRANT_UPSERT_BATCH`: points per upsert call; lower if timeouts occur over SSH.
- `PREFETCH_BATCHES`: queue buffering; higher = more resilience, higher RAM.
- `NUM_EMBED_WORKERS`: number of local model instances (only helpful if compute underutilized and VRAM available).
- `RESUME_INGESTION`: skip already processed `doc_id`s.
- `PURGE_COLLECTION`: delete and recreate collection for a clean slate.

## Known Limitations & Learnings

- Local runs are compute-bound for embedding; adding VRAM alone doesn’t lift docs/sec significantly.
- Chunking increases token volume and Qdrant points per document; use only when necessary.
- SSH tunnels can introduce latency; keep `timeout` generous and upsert batches moderate.
- Remote embeddings simplify ingestion and scale well, but require budget planning.


