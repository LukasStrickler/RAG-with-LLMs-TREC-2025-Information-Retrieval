"""Ingestion pipeline for RAG system.

Fetches documents from PostgreSQL, chunks them, embeds them using a local GPU,
and indexes them into Qdrant.

Enhancements:
 - Optional full purge of an existing collection before ingestion (--purge)
 - Resume capability: only missing chunks are (re)embedded (--no-resume disables)
 - Deterministic point IDs allow safe re-runs
"""

import sys
import os
import uuid
import argparse
from typing import List, Dict, Any, Set

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add shared module to path if not installed
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../shared/src"))
)

import torch  # type: ignore
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from db import Database

try:
    from shared.data.dataset import ChunkingSpec
except ImportError:
    print(
        "Warning: Could not import shared models. Ensure 'shared' package is installed or in path."
    )
    # Mock classes if import fails to allow script to run (or fail gracefully later)
    ChunkingSpec = Any

# Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "database": os.getenv("PG_DB", "postgres"),
    "user": os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASS"),
    "sslmode": os.getenv("DB_SSLMODE", "disable"),
}

QDRANT_HOST = os.getenv("QDRANT_HOST", "127.0.0.1")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Model Selection:
# We chose 'Qwen/Qwen3-Embedding-0.6B' based on the MTEB leaderboard.
# - Rank: Top Tier (Rank 6 on MTEB).
# - Performance: Significantly higher retrieval score (56.01) compared to BGE-large (39.06).
# - Size: 1024 dimensions (Same storage efficiency as BGE-large).
# - Context: Supports up to 32k tokens (Future proof, though we chunk at 512).
EMBEDDING_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Chunking Config
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


def setup_qdrant(
    client: QdrantClient, vector_size: int, collection_name: str, purge: bool = False
):
    """Create collection if not exists, optionally purging existing data.

    If purge=True and the collection exists, it will be deleted and recreated.
    """
    if purge and client.collection_exists(collection_name):
        print(f"Purging existing collection '{collection_name}'...")
        client.delete_collection(collection_name=collection_name)

    if not client.collection_exists(collection_name):
        print(
            f"Creating collection '{collection_name}' with vector size {vector_size}..."
        )
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE
            ),
        )
    else:
        print(f"Collection '{collection_name}' ready (existing).")


def chunk_text(text: str, tokenizer, chunk_size: int, overlap: int) -> List[str]:
    """
    Chunk text using the tokenizer.
    Simple sliding window approach.
    """
    if not text:
        return []

    tokens = tokenizer.tokenize(text)
    if len(tokens) <= chunk_size:
        return [text]

    chunks = []
    stride = chunk_size - overlap

    # This is a simplified chunking. For production, we might want to decode tokens back to text
    # carefully to avoid broken words, or use the tokenizer's built-in chunking if available.
    # SentenceTransformers doesn't expose a simple "chunk and decode" easily without some manual work.
    # For now, we'll use a character-based approximation or simple split if tokenizer is complex,
    # but let's try to do it right with token offsets if possible.

    # Simpler approach: Split by words/sentences or use a library like langchain.
    # Since we want to avoid extra deps, let's do a robust approximation.

    # Actually, sentence-transformers models usually truncate.
    # We need to manually slide the window.

    # Let's use the tokenizer to encode, then slice, then decode.
    token_ids = tokenizer.encode(text, add_special_tokens=False)

    for i in range(0, len(token_ids), stride):
        chunk_ids = token_ids[i : i + chunk_size]
        decoded_chunk = tokenizer.decode(chunk_ids)
        chunks.append(decoded_chunk)
        if i + chunk_size >= len(token_ids):
            break

    return chunks


def get_existing_chunk_indices(
    qdrant: QdrantClient, collection_name: str, doc_id: Any
) -> Set[int]:
    """Return set of existing chunk_index values for a given doc_id in the collection."""
    existing: Set[int] = set()
    try:
        scroll_res = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="doc_id", match=models.MatchValue(value=doc_id)
                    )
                ]
            ),
            limit=2048,  # assuming a doc won't exceed this chunk count
        )
        for point in scroll_res[0]:  # points list
            payload = point.payload or {}
            if "chunk_index" in payload:
                existing.add(int(payload["chunk_index"]))
    except Exception as e:
        # On error, treat as none existing
        print(f"Warning: could not scroll existing chunks for doc_id={doc_id}: {e}")
    return existing


def process_batch(
    batch_docs: List[Dict],
    model: SentenceTransformer,
    qdrant: QdrantClient,
    dataset_name: str,
    collection_name: str,
    resume: bool = True,
):
    """Process a batch of documents: chunk, embed missing chunks, upsert.

    If resume=True, existing chunks (by deterministic IDs) are skipped.
    """
    total_chunks_new = 0
    total_chunks_skipped = 0

    tokenizer = model.tokenizer

    for doc in batch_docs:
        doc_id = doc["id"]
        text = doc.get("body", "") or doc.get(
            "title", ""
        )  # Fallback to title if body empty
        if not text:
            continue

        # Chunking
        chunks = chunk_text(text, tokenizer, CHUNK_SIZE, CHUNK_OVERLAP)
        if not chunks:
            continue

        existing_indices: Set[int] = set()
        if resume:
            existing_indices = get_existing_chunk_indices(
                qdrant, collection_name, doc_id
            )

        missing_indices = [i for i in range(len(chunks)) if i not in existing_indices]

        if not missing_indices:
            total_chunks_skipped += len(chunks)
            continue  # fully ingested

        # Embed only missing chunks
        missing_texts = [chunks[i] for i in missing_indices]
        embeddings = model.encode(
            missing_texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True
        )

        points = []
        for local_pos, embedding in enumerate(embeddings):
            chunk_index = missing_indices[local_pos]
            point_id = str(
                uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_chunk_{chunk_index}")
            )
            meta = {
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "text": chunks[chunk_index],
                "dataset": dataset_name,
                "original_title": doc.get("title", ""),
                "url": doc.get("url", ""),
            }
            points.append(
                models.PointStruct(id=point_id, vector=embedding.tolist(), payload=meta)
            )

        qdrant.upsert(collection_name=collection_name, points=points)
        total_chunks_new += len(points)
        total_chunks_skipped += len(chunks) - len(points)

    return {"chunks_added": total_chunks_new, "chunks_skipped": total_chunks_skipped}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Embedding ingestion pipeline into Qdrant"
    )
    parser.add_argument(
        "--dataset", default="small", help="Name of dataset to ingest (default: small)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Number of documents per batch"
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Purge (delete & recreate) the collection before ingestion",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume; re-embed all chunks for all docs",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dataset_name = args.dataset
    collection_name = dataset_name  # Use dataset name as collection name
    batch_size = args.batch_size
    purge = args.purge
    resume = not args.no_resume

    print(f"Initializing ingestion pipeline on device: {DEVICE}")
    print(
        f"Dataset: {dataset_name} | Batch size: {batch_size} | Purge: {purge} | Resume: {resume}"
    )

    # 1. Connect to DB
    try:
        db = Database(DB_CONFIG)
        print("Connected to PostgreSQL.")
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return

    # 2. Connect to Qdrant
    try:
        qdrant = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            prefer_grpc=False,
            https=False,
            api_key=QDRANT_API_KEY,
        )
        print(f"Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
    except Exception as e:
        print(f"Failed to connect to Qdrant: {e}")
        return

    # 3. Load Model
    print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
    model = SentenceTransformer(
        EMBEDDING_MODEL_NAME, device=DEVICE, trust_remote_code=True
    )
    vector_size = model.get_sentence_embedding_dimension()
    print(f"Model loaded. Vector size: {vector_size}")

    # 4. Select Dataset
    dataset = db.get_dataset_by_name(dataset_name)
    if not dataset:
        print(f"Dataset '{dataset_name}' not found.")
        return
    print(f"Processing dataset: {dataset['name']} ({dataset['doc_count']} docs)")

    # 5. Setup Collection
    setup_qdrant(qdrant, vector_size, collection_name, purge=purge)

    # Log Spec (Mocking the logging for now, just printing)
    try:
        chunk_spec = ChunkingSpec(
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            tokenizer=EMBEDDING_MODEL_NAME,
            strategy="sliding",
        )
        print(f"Chunking Spec: {chunk_spec}")
    except Exception as e:
        print(f"Could not create ChunkingSpec: {e}")

    # 6. Processing Loop
    doc_ids = db.get_document_ids(dataset["id"])
    print(f"Found {len(doc_ids)} documents. Starting ingestion...")

    cumulative_added = 0
    cumulative_skipped = 0

    with tqdm(total=len(doc_ids), unit="docs") as pbar:
        for i in range(0, len(doc_ids), batch_size):
            batch_ids = doc_ids[i : i + batch_size]
            batch_docs = db.get_documents(batch_ids)
            stats = process_batch(
                batch_docs,
                model,
                qdrant,
                dataset["name"],
                collection_name,
                resume=resume,
            )
            cumulative_added += stats["chunks_added"]
            cumulative_skipped += stats["chunks_skipped"]
            pbar.update(len(batch_ids))
            pbar.set_postfix({"added": cumulative_added, "skipped": cumulative_skipped})

    print("Ingestion complete.")
    print(
        f"Chunks added: {cumulative_added} | Chunks skipped (already existed): {cumulative_skipped}"
    )
    db.close()


if __name__ == "__main__":
    main()
