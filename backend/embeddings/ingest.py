"""Ingestion pipeline for RAG system.

Fetches documents from PostgreSQL, embeds full documents using a local GPU,
and indexes them into Qdrant.

Enhancements:
 - Optional full purge of an existing collection before ingestion (--purge)
 - Resume capability: only missing documents are (re)embedded (--no-resume disables)
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

# Configuration - Local Docker Setup
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),  # Docker exposes PostgreSQL on 5433
    "database": os.getenv("PG_DB", "postgres"),
    "user": os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASS", "password"),  # Default from docker-compose.yml
    "sslmode": os.getenv("DB_SSLMODE", "disable"),
}

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))  # Docker exposes Qdrant on 6333
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)  # No API key for local Docker

# Model Selection:
# We chose 'Qwen/Qwen3-Embedding-8B' based on the MTEB leaderboard.
# - Rank: Top Tier (Rank 6 on MTEB).
# - Performance: Significantly higher retrieval score (56.01) compared to BGE-large (39.06).
# - Size: 1024 dimensions (Same storage efficiency as BGE-large).
# - Context: Supports up to 32k tokens (No chunking needed, embeds full documents).
EMBEDDING_MODEL_NAME = "Qwen/Qwen3-Embedding-8B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


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





def process_batch(
    batch_docs: List[Dict],
    model: SentenceTransformer,
    qdrant: QdrantClient,
    dataset_name: str,
    collection_name: str,
    resume: bool = True,
):
    """Process a batch of documents: embed full documents and upsert.

    If resume=True, existing documents (by deterministic IDs) are skipped.
    """
    docs_added = 0
    docs_skipped = 0

    # Prepare texts and check for existing documents
    texts_to_embed = []
    docs_to_process = []
    
    for doc in batch_docs:
        doc_id = doc["id"]
        text = doc.get("body", "") or doc.get(
            "title", ""
        )  # Fallback to title if body empty
        if not text:
            continue

        # Generate deterministic point ID based on doc_id
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(doc_id)))
        
        # Check if document already exists (if resume mode)
        if resume:
            try:
                existing = qdrant.retrieve(
                    collection_name=collection_name,
                    ids=[point_id],
                )
                if existing:
                    docs_skipped += 1
                    continue
            except Exception:
                # If collection doesn't exist or other error, proceed with embedding
                pass
        
        texts_to_embed.append(text)
        docs_to_process.append(doc)

    if not texts_to_embed:
        return {"docs_added": docs_added, "docs_skipped": docs_skipped}

    # Embed all documents in batch
    embeddings = model.encode(
        texts_to_embed, batch_size=1, show_progress_bar=False, convert_to_numpy=True
    )

    # Create points for upsert
    points = []
    for doc, embedding in zip(docs_to_process, embeddings):
        doc_id = doc["id"]
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(doc_id)))
        meta = {
            "doc_id": doc_id,
            "text": doc.get("body", "") or doc.get("title", ""),
            "dataset": dataset_name,
            "original_title": doc.get("title", ""),
            "url": doc.get("url", ""),
        }
        points.append(
            models.PointStruct(id=point_id, vector=embedding.tolist(), payload=meta)
        )

    qdrant.upsert(collection_name=collection_name, points=points)
    docs_added += len(points)

    return {"docs_added": docs_added, "docs_skipped": docs_skipped}


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
            cumulative_added += stats["docs_added"]
            cumulative_skipped += stats["docs_skipped"]
            pbar.update(len(batch_ids))
            pbar.set_postfix({"added": cumulative_added, "skipped": cumulative_skipped})

    print("Ingestion complete.")
    print(
        f"Documents added: {cumulative_added} | Documents skipped (already existed): {cumulative_skipped}"
    )
    db.close()


if __name__ == "__main__":
    main()
