# Embeddings & Ingestion Pipeline

This service handles the ingestion of documents from the PostgreSQL database into the Qdrant vector database.

## Overview

- **Source**: PostgreSQL (`documents` table)
- **Destination**: Qdrant (Collection: `small`)
- **Model**: `Qwen/Qwen3-Embedding-0.6B` (1024 dimensions)
- **Chunking**: Sliding window (Size: 512, Overlap: 50)

## Setup

1.  **Prerequisites**:
    *   Python 3.11+
    *   CUDA-capable GPU (Recommended)
    *   PostgreSQL (via SSH tunnel)
    *   Qdrant (via SSH tunnel)

2.  **Install Dependencies**:
    ```bash
    pipenv install
    ```
    *Note: This project uses `pipenv` for dependency management.*

3.  **SSH Tunnels**:
    Ensure you have the SSH tunnels running as described in the root README or search README.
    *   Postgres: Port 5433
    *   Qdrant: Port 6334 (GRPC)

## Usage

Run the ingestion pipeline:

```bash
pipenv run python ingest.py
```

## Configuration

*   **Database**: Configured in `ingest.py` (matches `backend/search` config).
*   **Qdrant**: Defaults to `localhost:6334`.
*   **Model**: Defaults to `Qwen/Qwen3-Embedding-0.6B`.

## Logging & Tracking

The pipeline uses `shared.data.dataset.ChunkingSpec` to validate chunking configurations.
Progress is displayed via `tqdm`.

## Detailed Pipeline Walkthrough

Here is a step-by-step explanation of how `ingest.py` works:

1.  **Initialization**:
    *   The script starts by connecting to the PostgreSQL database using the configuration copied from the search service.
    *   It connects to the Qdrant vector database running on `localhost:6334` (via SSH tunnel).
    *   It loads the `Qwen/Qwen3-Embedding-0.6B` model onto the GPU (if available). This model was chosen for its high retrieval performance and efficient 1024-dimensional vectors.

2.  **Dataset Selection**:
    *   It selects the "small" dataset from the database.
    *   It uses the dataset name ("small") as the Qdrant collection name.

3.  **Collection Setup**:
    *   The `setup_qdrant` function checks if a collection named "small" exists.
    *   If not, it creates it with `Cosine` distance metric and a vector size of 1024 (matching the model).

4.  **Processing Loop**:
    *   The script fetches all document IDs for the dataset.
    *   It iterates through these IDs in batches of 100 documents.
    *   For each batch, it fetches the full document content (title and body) from Postgres.

5.  **Batch Processing (`process_batch`)**:
    *   **Chunking**: Each document is split into smaller pieces using a "sliding window" strategy.
        *   `chunk_text` uses the model's tokenizer to convert text into token IDs.
        *   It slices these IDs into windows of 512 tokens with a 50-token overlap.
        *   It decodes these slices back into text strings. This ensures we don't cut words in half and maintain context across boundaries.
    *   **Embedding**: All chunks in the batch are sent to the GPU-accelerated model to generate 1024-dimensional vectors.
    *   **ID Generation**: A deterministic UUID is generated for each chunk using `uuid5(doc_id + chunk_index)`. This ensures that if we re-run the pipeline, we generate the exact same IDs and overwrite duplicates instead of creating ghosts.
    *   **Upsert**: The vectors, along with metadata (original text, doc_id, title, url), are uploaded to Qdrant in a single request.

6.  **Completion**:
    *   A progress bar (`tqdm`) shows the real-time status.
    *   Once all batches are processed, the database connection is closed.

## Architecture & Design Decisions

### Why Chunking? (Dense Passage Retrieval)

We employ a **Dense Passage Retrieval** strategy, which is the current industry standard for RAG systems.

1.  **Precision**: Embedding entire documents dilutes specific details. By chunking documents into 512-token passages, we create focused vectors. When a user queries for a specific detail, the relevant chunk matches with high similarity, whereas a whole-document vector might be too generic.
2.  **Context Management**: While LLMs have large context windows, we cannot feed them the entire corpus. Chunking allows us to retrieve only the most relevant "needles in the haystack."
3.  **Resolution**: We store the `doc_id` in the metadata of every chunk. This allows the downstream application to map a retrieved passage back to its parent document, potentially fetching surrounding context for the LLM generation phase.

This approach balances high retrieval accuracy with efficient storage and processing, making it ideal for the TREC RAG task.

---

## High-Performance Pipelined Ingestion

The ingestion pipeline uses a **3-stage pipelined architecture** with threading to maximize throughput by overlapping I/O-bound and compute-bound operations.

### Pipeline Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  PREFETCH       │     │  EMBED          │     │  UPSERT         │
│  (DB I/O)       │────▶│  (GPU Compute)  │────▶│  (Network I/O)  │
│                 │     │                 │     │                 │
│  Thread 1       │     │  Thread 2       │     │  Thread 3       │
│  PostgreSQL     │     │  SentenceTransf │     │  Qdrant         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
   doc_queue              points_queue            Progress Bar
   (prefetch_size)        (prefetch_size)         Updates
```

### How It Works

1. **Prefetch Thread**: Continuously fetches document batches from PostgreSQL and places them in `doc_queue`. This runs ahead of the GPU to ensure the embed thread never waits for data.

2. **Embed Thread**: Takes document batches from `doc_queue`, chunks the text, generates embeddings using the GPU, and places the resulting points in `points_queue`.

3. **Upsert Thread**: Takes points from `points_queue` and uploads them to Qdrant. Uses `wait=False` for async indexing.

### Why This Design?

| Component | Bottleneck Type | Solution |
|-----------|-----------------|----------|
| PostgreSQL fetch | Network I/O | Prefetch into queue |
| Embedding generation | GPU compute | Dedicated thread, large batch sizes |
| Qdrant upsert | Network I/O | Async upserts, batching |

By running these in parallel, we ensure:
- GPU never waits for database queries
- Network uploads happen while GPU is computing
- Memory is bounded by queue sizes

### Configuration Parameters

```python
# --- PIPELINE CONFIGURATION ---
BATCH_SIZE = 50           # Documents per processing batch
QDRANT_UPSERT_BATCH = 200 # Points per Qdrant upsert call
PREFETCH_BATCHES = 6      # Queue size between pipeline stages (see below)
NUM_EMBED_WORKERS = 1     # Number of parallel embedding workers (see Multi-GPU section)

# Resume capability
RESUME_INGESTION = True   # Resume from last processed doc_id
PURGE_COLLECTION = False  # Set True to start fresh
```

#### Understanding `PREFETCH_BATCHES` (Queue Buffering)

`PREFETCH_BATCHES` controls the **queue size** between all pipeline stages, not just prefetch:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  PREFETCH       │     │  EMBED          │     │  UPSERT         │
│  (DB I/O)       │────▶│  (GPU Compute)  │────▶│  (Network I/O)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       
        ▼                       ▼                       
   doc_queue                points_queue            
   maxsize = 6×workers      maxsize = 6×workers     
```

**What it controls:**

| Queue | Purpose | Effect of `PREFETCH_BATCHES=6` |
|-------|---------|-------------------------------|
| `doc_queue` | Holds fetched documents waiting for embedding | Prefetch can run up to 6 batches ahead of GPU |
| `points_queue` | Holds embedded points waiting for upsert | GPU can run up to 6 batches ahead of Qdrant |

**Behavior:**

1. **If prefetch is fast, GPU is slow**: The `doc_queue` fills up (up to 6 batches), then prefetch blocks waiting for GPU to consume
2. **If GPU is fast, upsert is slow**: The `points_queue` fills up (up to 6 batches), then GPU blocks waiting for Qdrant to consume
3. **Buffering benefit**: Provides slack so temporary slowdowns in one stage don't immediately stall others

**Memory tradeoff:** Higher values = more documents buffered in RAM, but more resilience to latency spikes.

### Resume Capability

The pipeline supports **resumable ingestion**:

1. On startup, it queries Qdrant for all existing `doc_id` values
2. Finds the maximum `doc_id` (lexicographically)
3. Queries PostgreSQL for documents with `doc_id > last_processed`
4. Only processes new documents

This means you can:
- Stop and restart the notebook at any time
- Resume after crashes without reprocessing
- Add new documents to the database and only ingest the delta

### Thread Safety

- **PostgreSQL**: Uses `ThreadedConnectionPool` for thread-safe database access
- **Qdrant**: Client is thread-safe; upserts use `wait=False` for async operation
- **Queues**: Python's `queue.Queue` provides thread-safe producer-consumer pattern
- **Stats**: Protected by `threading.Lock()` for accurate progress tracking

### Multi-Model GPU Support (A100 / Large VRAM)

For GPUs with large VRAM (e.g., A100 40GB/80GB), the pipeline supports **multiple parallel embedding workers**, each with its own model instance:

```python
NUM_EMBED_WORKERS = 4  # Load 4 model instances for parallel embedding
```

**Architecture with Multiple Workers:**

```
┌─────────────────┐     ┌─────────────────┐
│  PREFETCH       │     │  EMBED Worker 0 │──┐
│  (DB I/O)       │────▶│  (GPU Compute)  │  │
│                 │     └─────────────────┘  │     ┌─────────────────┐
│  Thread 1       │     ┌─────────────────┐  ├────▶│  UPSERT         │
│  PostgreSQL     │────▶│  EMBED Worker 1 │──┤     │  (Network I/O)  │
└─────────────────┘     │  (GPU Compute)  │  │     │                 │
        │               └─────────────────┘  │     │  Thread N+2     │
        ▼               ┌─────────────────┐  │     │  Qdrant         │
   doc_queue ──────────▶│  EMBED Worker N │──┘     └─────────────────┘
   (prefetch * workers) │  (GPU Compute)  │               │
                        └─────────────────┘               ▼
                                                    Progress Bar
```

**VRAM Requirements (Qwen 0.6B):**

| Workers | Approximate VRAM | Recommended GPU |
|---------|------------------|-----------------|
| 1 | ~3 GB | GTX 1080, RTX 3060 |
| 2 | ~5 GB | RTX 3070, RTX 4070 |
| 4 | ~10 GB | RTX 3090, RTX 4090 |
| 8 | ~20 GB | A100 40GB |
| 16 | ~40 GB | A100 80GB |

**When to Use Multiple Workers:**

| Scenario | `NUM_EMBED_WORKERS` | Reason |
|----------|---------------------|--------|
| Consumer GPU (8-12GB) | 1 | VRAM limited; single model optimal |
| RTX 3090/4090 (24GB) | 2-4 | Extra VRAM available for parallelism |
| A100 40GB | 4-8 | Plenty of VRAM; maximize throughput |
| A100 80GB | 8-16 | Full utilization of available memory |

**How It Works:**
- Each worker thread loads its own `SentenceTransformer` model instance
- Workers compete for batches from the shared `doc_queue`
- All workers output to the same `points_queue` for upserting
- The GPU scheduler interleaves work across model instances
- Net effect: higher GPU utilization when I/O is a factor

**Startup Output:**
```
Loading 4 embedding model instance(s): Qwen/Qwen3-Embedding-0.6B...
  Loading model 1/4...
  Loading model 2/4...
  Loading model 3/4...
  Loading model 4/4...
✅ Loaded 4 model instance(s). Vector size: 1024
   GPU Memory: 9.42 GB allocated, 10.00 GB reserved
```

### Single Model Instance Design

The default implementation uses **one model instance on the GPU** (`NUM_EMBED_WORKERS=1`). This is appropriate for:

| Scenario | Multiple Models? | Reason |
|----------|------------------|--------|
| Consumer GPU (8-24GB) | ❌ No | VRAM limited; single model saturates compute |
| Small model, limited VRAM | ❌ No | Memory bandwidth contention negates benefits |
| A100 / Large VRAM | ✅ Yes | Extra VRAM enables parallel model instances |
| Multiple GPUs | ✅ Yes | One model per GPU would be optimal (future work) |
| CPU only | ✅ Yes | Multiple instances can utilize multiple cores |

For the Qwen 0.6B model on a single consumer GPU, the embedding generation saturates GPU compute. The pipelining ensures the GPU is never idle waiting for I/O, which is the optimal configuration.

### Performance Tuning

**If GPU utilization is low (<90%)**:
- Increase `BATCH_SIZE` (more documents per batch)
- Increase `embed_batch_size` in `_embed_worker` (currently 64)

**If running out of VRAM**:
- Decrease `BATCH_SIZE`
- The pipeline auto-falls back to `batch_size=16` on OOM errors

**If Qdrant times out**:
- Decrease `QDRANT_UPSERT_BATCH`
- The `timeout=300` should handle most cases over SSH tunnels

**Typical Performance**: 30-80 docs/second depending on document length and GPU capability.

### Bottleneck Analysis (Progress Bar Metrics)

The progress bar displays **per-stage throughput** to help identify bottlenecks in real-time:

```
Ingesting:  45%|████▌     | 4500/10000 [02:15<02:45, 33.2docs/s, chunks=18234, fetch=85d/s, embed=42d/s, upsert=120d/s, batch=90/200]
```

**Metrics explained:**

| Metric | Description |
|--------|-------------|
| `fetch=85d/s` | DB prefetch speed (docs/sec from PostgreSQL) |
| `embed=42d/s` | Embedding speed (docs/sec through GPU) |
| `upsert=120d/s` | Qdrant upsert speed (docs/sec to vector DB) |
| `chunks=18234` | Total chunks created so far |
| `batch=90/200` | Current batch / total batches |

**Interpreting bottlenecks:**

| Pattern | Bottleneck | Solution |
|---------|------------|----------|
| `fetch` << others | Database I/O | Increase `PREFETCH_BATCHES`, check SSH tunnel latency |
| `embed` << others | GPU compute | Increase `NUM_EMBED_WORKERS` (if VRAM available), or use faster GPU |
| `upsert` << others | Network/Qdrant | Decrease `QDRANT_UPSERT_BATCH`, check network latency |
| All roughly equal | Balanced | Pipeline is well-tuned ✅ |

The metrics use a **rolling average of the last 10 batches** for stability.
