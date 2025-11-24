"""
Ingestion pipeline for RAG system.
Fetches documents from PostgreSQL, chunks them, embeds them using a local GPU,
and indexes them into Qdrant.
"""

import sys
import os
import uuid
from typing import List, Dict, Any
from datetime import date

# Add shared module to path if not installed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../shared/src")))

import torch
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from db import Database
try:
    from shared.data.dataset import DatasetSpec, ChunkingSpec
    from shared.data.index import IndexTarget
    from shared.enums import IndexKind
except ImportError:
    print("Warning: Could not import shared models. Ensure 'shared' package is installed or in path.")
    # Mock classes if import fails to allow script to run (or fail gracefully later)
    DatasetSpec = Any
    ChunkingSpec = Any
    IndexTarget = Any
    IndexKind = Any

# Configuration
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5433,
    'database': 'postgres',
    'user': 'postgres',
    'password': '9IiVCS9s9ejH3QKO1aaFLyRzjAoTF87zZwp7cK0y0ofZoDvdq2uxF5OLm1hyAnRl',
    'sslmode': 'disable'
}

QDRANT_HOST = "127.0.0.1"
QDRANT_PORT = 6333
QDRANT_API_KEY = "DkJsZtSFdDjCClMz2vv5qAJmmrq2Si74"

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

def setup_qdrant(client: QdrantClient, vector_size: int, collection_name: str):
    """Create collection if not exists."""
    if not client.collection_exists(collection_name):
        print(f"Creating collection '{collection_name}' with vector size {vector_size}...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE
            )
        )
    else:
        print(f"Collection '{collection_name}' already exists.")

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
        chunk_text = tokenizer.decode(chunk_ids)
        chunks.append(chunk_text)
        
        if i + chunk_size >= len(token_ids):
            break
            
    return chunks

def process_batch(
    batch_docs: List[Dict], 
    model: SentenceTransformer, 
    qdrant: QdrantClient,
    dataset_name: str,
    collection_name: str
):
    """
    Process a batch of documents: chunk, embed, upsert.
    """
    points = []
    
    # Prepare all chunks for the batch
    all_chunks = []
    chunk_metadata = []
    
    for doc in batch_docs:
        doc_id = doc['id']
        text = doc.get('body', '') or doc.get('title', '') # Fallback to title if body empty
        
        # Chunking
        # Access tokenizer from the underlying transformer model
        tokenizer = model.tokenizer
        chunks = chunk_text(text, tokenizer, CHUNK_SIZE, CHUNK_OVERLAP)
        
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            chunk_metadata.append({
                "doc_id": doc_id,
                "chunk_index": i,
                "text": chunk,
                "dataset": dataset_name,
                "original_title": doc.get('title', ''),
                "url": doc.get('url', '')
            })
            
    if not all_chunks:
        return

    # Embed
    embeddings = model.encode(all_chunks, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
    
    # Prepare points for Qdrant
    for i, embedding in enumerate(embeddings):
        meta = chunk_metadata[i]
        # Create a deterministic ID for the chunk
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{meta['doc_id']}_chunk_{meta['chunk_index']}"))
        
        points.append(models.PointStruct(
            id=point_id,
            vector=embedding.tolist(),
            payload=meta
        ))
        
    # Upsert
    qdrant.upsert(
        collection_name=collection_name,
        points=points
    )

def main():
    print(f"Initializing ingestion pipeline on device: {DEVICE}")
    
    # 1. Connect to DB
    try:
        db = Database(DB_CONFIG)
        print("Connected to PostgreSQL.")
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return

    # 2. Connect to Qdrant
    try:
        # Using HTTP because the SSH tunnel forwards to the remote HTTP port (6333)
        # NOTE: If you are using an SSH tunnel, ensure it is forwarding to the correct remote IP.
        # If you see "Connection refused", it means the tunnel is not reaching the Qdrant service.
        # Try checking the remote IP of the Qdrant container.
        # We set https=False because the tunnel is a raw TCP forward to an HTTP port, not HTTPS.
        qdrant = QdrantClient(
            host=QDRANT_HOST, 
            port=QDRANT_PORT, 
            prefer_grpc=False, 
            https=False,
            api_key=QDRANT_API_KEY
        )
        print(f"Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
    except Exception as e:
        print(f"Failed to connect to Qdrant: {e}")
        return

    # 3. Load Model
    print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=DEVICE, trust_remote_code=True)
    vector_size = model.get_sentence_embedding_dimension()
    print(f"Model loaded. Vector size: {vector_size}")

    # 5. Select Dataset
    dataset_name = "small" # As requested
    collection_name = dataset_name # Use dataset name as collection name
    
    dataset = db.get_dataset_by_name(dataset_name)
    if not dataset:
        print(f"Dataset '{dataset_name}' not found.")
        return
    
    print(f"Processing dataset: {dataset['name']} ({dataset['doc_count']} docs)")
    
    # 4. Setup Collection (Moved after dataset selection to use name)
    setup_qdrant(qdrant, vector_size, collection_name)
    
    # Log Spec (Mocking the logging for now, just printing)
    try:
        chunk_spec = ChunkingSpec(
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            tokenizer=EMBEDDING_MODEL_NAME,
            strategy="sliding"
        )
        print(f"Chunking Spec: {chunk_spec}")
        
        # We would normally save this to the metadata store
    except Exception as e:
        print(f"Could not create ChunkingSpec: {e}")

    # 6. Processing Loop
    batch_size = 100 # Doc batch size
    doc_ids = db.get_document_ids(dataset['id'])
    
    print(f"Found {len(doc_ids)} documents. Starting ingestion...")
    
    with tqdm(total=len(doc_ids), unit="docs") as pbar:
        for i in range(0, len(doc_ids), batch_size):
            batch_ids = doc_ids[i : i + batch_size]
            batch_docs = db.get_documents(batch_ids)
            
            process_batch(batch_docs, model, qdrant, dataset['name'], collection_name)
            pbar.update(len(batch_ids))
            
    print("Ingestion complete.")
    db.close()

if __name__ == "__main__":
    main()
