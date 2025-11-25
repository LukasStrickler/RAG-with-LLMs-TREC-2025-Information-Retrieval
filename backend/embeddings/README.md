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
