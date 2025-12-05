import os
import time
import uuid
import logging
import requests
import threading
import queue
from typing import List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from psycopg2 import pool
from sshtunnel import SSHTunnelForwarder
from qdrant_client import QdrantClient
from qdrant_client.http import models
from tqdm import tqdm
import paramiko
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================================
# 1. GLOBAL CONFIGURATION
# ==========================================

# --- OPENROUTER API ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/embeddings")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
PRICE_PER_1M_TOKENS = float(os.getenv("PRICE_PER_1M_TOKENS", "0.05"))

# --- SSH / NETWORK ---
SSH_USE = os.getenv("SSH_USE", "false").lower() == "true"
SSH_HOST = os.getenv("SSH_HOST")
SSH_USER = os.getenv("SSH_USER")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")

# --- REMOTE IPs ---
PG_REMOTE_IP = os.getenv("PG_REMOTE_IP", "10.0.1.7")
QDRANT_REMOTE_IP = os.getenv("QDRANT_REMOTE_IP", "10.0.3.2")

# --- LOCAL PORTS ---
PG_LOCAL_PORT = int(os.getenv("PG_LOCAL_PORT", "5432"))
QDRANT_HTTP_PORT = int(os.getenv("QDRANT_HTTP_PORT", "6333"))

# --- POSTGRES AUTH ---
PG_DB = os.getenv("PG_DB", "postgres")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASS")

# --- PIPELINE CONFIG ---
DATASET_NAME = os.getenv("DATASET_NAME", "small")
COLLECTION_NAME = os.getenv("SOURCE_COLLECTION", "small_openrouter_nc")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))
MAX_TOKENS_PER_DOC = int(os.getenv("MAX_TOKENS_PER_DOC", "30000"))  # Max tokens before truncating (model limit is 33k)

# --- QUEUE CONFIG ---
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "20"))  # Backpressure limit: Pause API calls if 5 batches are waiting for upsert
NUM_EMBED_WORKERS = int(os.getenv("NUM_EMBED_WORKERS", "15"))  # Number of threads making API calls

# --- QDRANT CONFIG ---
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_UPSERT_BATCH_SIZE = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", "300"))  # Max points per Qdrant upsert (to avoid payload size limits)


# --- PATCH PARAMIKO ---
if not hasattr(paramiko, "DSSKey"):
    class DSSKey(paramiko.PKey):
        pass
    paramiko.DSSKey = DSSKey


# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress verbose HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ==========================================
# 2. HELPER CLASSES
# ==========================================

class Database:
    def __init__(self, port):
        self.pool = pool.ThreadedConnectionPool(
            1, 20,
            # host='127.0.0.1', port=port,
            host='10.0.1.7', port=port,   # When running on server directly
            database=PG_DB, user=PG_USER, password=PG_PASS
        )
        self._local = threading.local()

    def get_conn(self):
        if not hasattr(self._local, 'conn') or self._local.conn.closed:
            self._local.conn = self.pool.getconn()
            self._local.conn.set_session(readonly=True, autocommit=True)
        return self._local.conn

    def get_dataset_id(self, name: str):
        with self.get_conn().cursor() as cur:
            cur.execute("SELECT id, name FROM dataset WHERE name = %s", (name,))
            return cur.fetchone()

    def get_document_ids(self, dataset_id):
        with self.get_conn().cursor() as cur:
            cur.execute("SELECT document_id FROM document_in_dataset WHERE dataset_id = %s", (dataset_id,))
            return [str(row[0]) for row in cur.fetchall()] 

    def get_documents_by_ids(self, doc_ids):
        if not doc_ids: return []
        with self.get_conn().cursor() as cur:
            cur.execute("SELECT id, title, body, url FROM documents WHERE id = ANY(%s)", (doc_ids,))
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self):
        self.pool.closeall()

class PipelineStats:
    def __init__(self):
        self.lock = threading.Lock()
        # Accumulators for the current window
        self.fetch_time = 0.0
        self.fetch_docs = 0
        
        self.embed_time = 0.0
        self.embed_docs = 0
        
        self.upsert_time = 0.0
        self.upsert_docs = 0
        
        # Last known rates (for display stability)
        self.last_fetch_rate = 0.0
        self.last_embed_rate = 0.0
        self.last_upsert_rate = 0.0

    def update_fetch(self, t, n):
        with self.lock:
            self.fetch_time += t
            self.fetch_docs += n

    def update_embed(self, t, n):
        with self.lock:
            self.embed_time += t
            self.embed_docs += n

    def update_upsert(self, t, n):
        with self.lock:
            self.upsert_time += t
            self.upsert_docs += n
            
    def get_and_reset_rates(self, num_embed_workers):
        with self.lock:
            # Fetch
            if self.fetch_time > 0:
                self.last_fetch_rate = self.fetch_docs / self.fetch_time
            # Reset
            self.fetch_time = 0
            self.fetch_docs = 0
            
            # Embed
            if self.embed_time > 0:
                # Average rate per thread * num_threads
                avg_thread_rate = self.embed_docs / self.embed_time
                self.last_embed_rate = avg_thread_rate * num_embed_workers
            self.embed_time = 0
            self.embed_docs = 0
            
            # Upsert
            if self.upsert_time > 0:
                self.last_upsert_rate = self.upsert_docs / self.upsert_time
            self.upsert_time = 0
            self.upsert_docs = 0
            
            return self.last_fetch_rate, self.last_embed_rate, self.last_upsert_rate

# ==========================================
# 3. CORE FUNCTIONS
# ==========================================

def get_openrouter_embeddings(texts: List[str], retries=10, backoff=1.0, max_backoff=30.0) -> List[List[float]]:
    """Generates embeddings via OpenRouter API using batching with backoff and splitting."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts
    }
    
    def get_wait_time(attempt):
        """Calculate wait time with exponential backoff, capped at max_backoff."""
        return min(backoff * (2 ** attempt), max_backoff)

    for attempt in range(retries + 1):
        try:
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
            
            if response.status_code == 413 or ("payload" in response.text.lower() and "larger than allowed" in response.text.lower()):
                if len(texts) <= 1:
                    logger.error("Single document too large for API limit.")
                    return []
                
                logger.warning(f"Payload too large ({len(texts)} texts). Splitting batch...")
                mid = len(texts) // 2
                left = get_openrouter_embeddings(texts[:mid], retries, backoff)
                right = get_openrouter_embeddings(texts[mid:], retries, backoff)
                
                if len(left) == len(texts[:mid]) and len(right) == len(texts[mid:]):
                    return left + right
                return []

            if response.status_code == 402:
                logger.critical("💸 402 Payment Required - Out of credits! Exiting...")
                import sys
                sys.exit(1)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'error' in data:
                        error_msg = str(data['error'])
                        error_code = data['error'].get('code') if isinstance(data['error'], dict) else None
                        
                        # Transient errors that should be retried
                        is_transient = (
                            'rate limit' in error_msg.lower() or
                            'no successful provider' in error_msg.lower() or
                            error_code in [404, 429, 500, 502, 503, 504]
                        )
                        
                        if is_transient:
                            wait_time = get_wait_time(attempt)
                            logger.warning(f"Transient API error (attempt {attempt+1}/{retries+1}): {data['error']}. Retrying in {wait_time:.2f}s...")
                            time.sleep(wait_time)
                            continue
                        
                        logger.error(f"API returned 200 but with error: {data['error']}")
                        return []

                    if 'data' not in data:
                        raise ValueError(f"Missing 'data' in response keys: {list(data.keys())}")
                    
                    sorted_data = sorted(data['data'], key=lambda x: x['index'])
                    return [item['embedding'] for item in sorted_data]
                except (requests.exceptions.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                    # JSON parse error or malformed response - likely truncated, retry
                    snippet = response.text.strip()
                    if not snippet:
                        snippet = "[Empty or Whitespace only]"
                    else:
                        snippet = snippet[:500]
                    
                    wait_time = get_wait_time(attempt)
                    logger.warning(f"Malformed response (attempt {attempt+1}/{retries+1}): {e}. Retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
            
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = min(float(retry_after), max_backoff)
                    except ValueError:
                        wait_time = get_wait_time(attempt)
                else:
                    wait_time = get_wait_time(attempt)
                
                logger.warning(f"Rate Limit (429) (attempt {attempt+1}/{retries+1}). Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue

            if response.status_code >= 500:
                wait_time = get_wait_time(attempt)
                logger.warning(f"Server Error {response.status_code} (attempt {attempt+1}/{retries+1}). Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            
            logger.error(f"Client Error {response.status_code}: {response.text[:500]}")
            return []

        except requests.exceptions.RequestException as e:
            wait_time = get_wait_time(attempt)
            logger.warning(f"Network Request Failed (attempt {attempt+1}/{retries+1}): {e}. Retrying in {wait_time:.2f}s...")
            time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Unexpected Error: {e}")
            return []
            
            logger.error(f"Max retries ({retries}) exceeded for batch of {len(texts)} texts.")
    return []

def get_existing_doc_ids(qdrant: QdrantClient) -> set:
    print("🔎 Checking for existing documents in Qdrant (Resume Logic)...")
    if not qdrant.collection_exists(COLLECTION_NAME):
        return set()

    existing_ids = set()
    next_offset = None
    
    while True:
        records, next_offset = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            with_payload=['doc_id'], 
            with_vectors=False,
            limit=10000, 
            offset=next_offset
        )
        
        for record in records:
            if record.payload and 'doc_id' in record.payload:
                existing_ids.add(str(record.payload['doc_id']))
        
        if next_offset is None:
            break
            
    print(f"✅ Found {len(existing_ids):,} existing documents.")
    return existing_ids

def estimate_costs(db: Database, doc_ids: List[str]):
    print("\n--- 💰 COST ESTIMATION ---")
    if not doc_ids: return
    
    # Sample 100 docs
    sample_ids = doc_ids[:10000]
    docs = db.get_documents_by_ids(sample_ids)
    
    total_chars = sum(len((d.get('title') or "") + (d.get('body') or "")) for d in docs)
    avg_chars = total_chars / len(docs) if docs else 0
    avg_tokens = avg_chars / 3.5
    
    total_est_tokens = avg_tokens * len(doc_ids)
    est_price = (total_est_tokens / 1_000_000) * PRICE_PER_1M_TOKENS
    
    print(f"Docs to Process: {len(doc_ids):,}")
    print(f"Avg Tokens/Doc:  {avg_tokens:.0f}")
    print(f"Total Tokens:    {total_est_tokens:,.0f}")
    print(f"Est. Cost:       ${est_price:.4f}")
    print("---------------------------")
    input("Press Enter to start ingestion (Ctrl+C to cancel)...")

# ==========================================
# 4. PIPELINE WORKERS
# ==========================================

def prefetch_worker(db: Database, doc_ids: List[str], doc_queue: queue.Queue, stats: PipelineStats):
    """Thread 1: Fetches documents from DB and puts them in doc_queue."""
    try:
        for i in range(0, len(doc_ids), BATCH_SIZE):
            batch_ids = doc_ids[i:i+BATCH_SIZE]
            
            start_time = time.time()
            docs = db.get_documents_by_ids(batch_ids)
            duration = time.time() - start_time
            
            if docs:
                doc_queue.put(docs) # Blocks if queue is full
                stats.update_fetch(duration, len(docs))
    except Exception as e:
        logger.error(f"Prefetch worker failed: {e}")
    finally:
        # Signal end of fetching
        for _ in range(NUM_EMBED_WORKERS):
            doc_queue.put(None)

def embed_worker(doc_queue: queue.Queue, points_queue: queue.Queue, stats: PipelineStats):
    """Thread 2: Takes docs, chunks, calls API, puts points in points_queue."""
    while True:
        docs = doc_queue.get()
        if docs is None:
            doc_queue.task_done()
            break # Sentinel received
        
        try:
            texts_to_embed = []
            metadatas = []
            
            # No chunking - embed full documents
            max_chars = int(MAX_TOKENS_PER_DOC * 3.5)  # Approximate char limit
            
            for doc in docs:
                content = (doc.get('title') or "") + "\n\n" + (doc.get('body') or "")
                # Truncate if too long (shouldn't happen often with 30k token limit)
                if len(content) > max_chars:
                    content = content[:max_chars]
                
                texts_to_embed.append(content)
                metadatas.append({
                    "doc_id": str(doc['id']),
                    "dataset": DATASET_NAME
                })

            if texts_to_embed:
                start_time = time.time()
                
                # Send all docs at once - get_openrouter_embeddings will auto-split if payload too large
                all_embeddings = get_openrouter_embeddings(texts_to_embed)

                duration = time.time() - start_time
                
                if all_embeddings and len(all_embeddings) == len(texts_to_embed):
                    points = []
                    for i, emb in enumerate(all_embeddings):
                        meta = metadatas[i]
                        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, meta['doc_id']))
                        points.append(models.PointStruct(id=point_id, vector=emb, payload=meta))
                    
                    # This blocks if points_queue is full (Backpressure)
                    points_queue.put((points, len(docs))) 
                    stats.update_embed(duration, len(docs))
                else:
                    logger.error(f"Embedding mismatch or failure: {len(all_embeddings)} vs {len(texts_to_embed)}")
                    # We might want to handle this better, but for now we skip
        except Exception as e:
            logger.error(f"Embed worker failed: {e}")
        finally:
            doc_queue.task_done()

def upsert_worker(qdrant: QdrantClient, points_queue: queue.Queue, pbar: tqdm, stats: PipelineStats, doc_queue: queue.Queue):
    """Thread 3: Takes points and upserts to Qdrant."""
    last_time = time.time()
    
    def do_upsert(points_batch):
        """Upsert a single batch with retries."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                qdrant.upsert(collection_name=COLLECTION_NAME, points=points_batch, wait=True)
                return time.time() - start_time
            except Exception as e:
                error_str = str(e)
                # Check if it's a payload size error - split and retry
                if "payload" in error_str.lower() and "larger than allowed" in error_str.lower():
                    if len(points_batch) <= 1:
                        logger.error(f"Single point too large for Qdrant. Skipping.")
                        return 0
                    logger.warning(f"Qdrant payload too large ({len(points_batch)} points). Splitting...")
                    mid = len(points_batch) // 2
                    t1 = do_upsert(points_batch[:mid])
                    t2 = do_upsert(points_batch[mid:])
                    return t1 + t2
                
                wait = 2 ** attempt
                logger.warning(f"Upsert failed (Attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
        
        logger.error(f"Failed to upsert batch after {max_retries} attempts. Dropping batch.")
        return 0
    
    while True:
        try:
            # Use timeout to allow periodic stats updates even if queue is empty/slow
            item = points_queue.get(timeout=0.5)
        except queue.Empty:
            # Update stats even if no new upserts
            pass
        else:
            if item is None:
                points_queue.task_done()
                break
                
            points, num_docs = item
            
            # Batch upserts to avoid Qdrant payload size limits
            total_duration = 0
            for i in range(0, len(points), QDRANT_UPSERT_BATCH_SIZE):
                batch = points[i:i + QDRANT_UPSERT_BATCH_SIZE]
                total_duration += do_upsert(batch)
            
            pbar.update(num_docs)
            stats.update_upsert(total_duration, num_docs)
            points_queue.task_done()

        # Update stats every ~0.5s
        now = time.time()
        dt = now - last_time
        if dt > 0.5:
            f_rate, e_rate, u_rate = stats.get_and_reset_rates(NUM_EMBED_WORKERS)
            
            pbar.set_postfix({
                "fetch": f"{f_rate:.1f}/s",
                "embed": f"{e_rate:.1f}/s",
                "upsert": f"{u_rate:.1f}/s",
                "q_in": doc_queue.qsize(),
                "q_out": points_queue.qsize()
            })
            
            last_time = now

# ==========================================
# 5. MAIN EXECUTION
# ==========================================

def execute_pipeline():
    db = Database(PG_LOCAL_PORT)
    qdrant = QdrantClient(
        # host='127.0.0.1', 
        host='10.0.3.2',  # When running on server directly
        port=QDRANT_HTTP_PORT, 
        api_key=QDRANT_API_KEY, 
        https=False,
        timeout=120
    )

    try:
        # 1. Setup Collection
        if not qdrant.collection_exists(COLLECTION_NAME):
            dummy = get_openrouter_embeddings(["test"])
            if dummy:
                qdrant.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(size=len(dummy[0]), distance=models.Distance.COSINE)
                )
        
        qdrant.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="doc_id",
            field_schema=models.PayloadSchemaType.KEYWORD
        )

        # 2. Get Work
        ds_info = db.get_dataset_id(DATASET_NAME)
        if not ds_info: return
        
        all_ids = set(db.get_document_ids(ds_info[0]))
        existing_ids = get_existing_doc_ids(qdrant)
        ids_to_process = list(all_ids - existing_ids)
        
        if not ids_to_process:
            print("🎉 All documents already ingested!")
            return

        estimate_costs(db, ids_to_process)

        print(f"🚀 Starting Pipeline for {len(ids_to_process)} documents...")
        
        # 3. Initialize Queues & Stats
        doc_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE * 2) # Buffer for fetching
        points_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)  # Buffer for upserts (Backpressure)
        stats = PipelineStats()

        # 4. Start Threads
        threads = []
        
        # Prefetch Thread
        t_prefetch = threading.Thread(target=prefetch_worker, args=(db, ids_to_process, doc_queue, stats))
        t_prefetch.start()
        threads.append(t_prefetch)
        
        # Embed Threads
        for _ in range(NUM_EMBED_WORKERS):
            t_embed = threading.Thread(target=embed_worker, args=(doc_queue, points_queue, stats))
            t_embed.start()
            threads.append(t_embed)
        
        # Upsert Thread (Main thread can also do this, but let's use a separate one for clarity)
        # We need a progress bar, so we'll pass it to the worker
        pbar = tqdm(total=len(ids_to_process))
        t_upsert = threading.Thread(target=upsert_worker, args=(qdrant, points_queue, pbar, stats, doc_queue))
        t_upsert.start()
        threads.append(t_upsert)

        # 5. Wait for completion
        t_prefetch.join() # Wait for all docs to be fetched
        
        for i in range(NUM_EMBED_WORKERS):
            threads[i+1].join() # Wait for all embeddings to finish
        
        points_queue.put(None) # Signal upsert thread to stop
        t_upsert.join()
        
        pbar.close()
        print("✅ Ingestion Complete")

    finally:
        db.close()


def main():
    if SSH_USE:
        with SSHTunnelForwarder(
            (SSH_HOST, 22),
            ssh_username=SSH_USER,
            ssh_password=SSH_PASSWORD,
            remote_bind_addresses=[(PG_REMOTE_IP, 5432), (QDRANT_REMOTE_IP, 6333)],
            local_bind_addresses=[('127.0.0.1', PG_LOCAL_PORT), ('127.0.0.1', QDRANT_HTTP_PORT)]
        ) as tunnel:
            print(f"🔌 Tunnel Active")
            execute_pipeline()
    else:
        # Direct connection (no SSH tunnel needed, e.g., running on the server itself)
        execute_pipeline()
        

if __name__ == "__main__":
    main()