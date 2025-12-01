import os
import time
import uuid
import logging
import requests
import threading
import queue
from typing import List, Any, Set, Dict, Tuple

from psycopg2 import pool
from sshtunnel import SSHTunnelForwarder
from qdrant_client import QdrantClient
from qdrant_client.http import models
from tqdm import tqdm
import paramiko

# ==========================================
# 1. GLOBAL CONFIGURATION
# ==========================================

# --- OPENROUTER API ---
OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b" 
PRICE_PER_1M_TOKENS = 0.05 

# --- SSH / NETWORK ---
SSH_USE = False
SSH_HOST = "95.216.74.52"
SSH_USER = "lean"
SSH_PASSWORD = "l+VHTcsLfsdEiXlv"

# --- REMOTE IPs ---
PG_REMOTE_IP = "10.0.1.7"
QDRANT_REMOTE_IP = "10.0.3.2"

# --- LOCAL PORTS ---
PG_LOCAL_PORT = 5432
QDRANT_HTTP_PORT = 6333

# --- POSTGRES AUTH ---
PG_DB = "postgres"
PG_USER = "postgres"
PG_PASS = "9IiVCS9s9ejH3QKO1aaFLyRzjAoTF87zZwp7cK0y0ofZoDvdq2uxF5OLm1hyAnRl"

# --- PIPELINE CONFIG ---
QRELS_FILE = "data/dl23-qrels.txt"  # Path to qrels file
SOURCE_COLLECTION = "small_openrouter_nc"  # Existing collection to check for embeddings
TARGET_COLLECTION = "qrels"  # New collection for qrels embeddings
BATCH_SIZE = 200
MAX_TOKENS_PER_DOC = 30000  # Max tokens before truncating (model limit is 33k)

# --- QUEUE CONFIG ---
MAX_QUEUE_SIZE = 20 # Backpressure limit: Pause API calls if batches are waiting for upsert
NUM_EMBED_WORKERS = 15 # Number of threads making API calls

# --- QDRANT CONFIG ---
QDRANT_UPSERT_BATCH_SIZE = 300  # Max points per Qdrant upsert (to avoid payload size limits)


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
# 2. HELPER CLASSES & FUNCTIONS
# ==========================================

class Database:
    """PostgreSQL connection pool for fetching document content."""
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

    def get_documents_by_ids(self, doc_ids):
        """Fetch documents by their IDs. Returns list of dicts with id, title, body, url."""
        if not doc_ids: return []
        with self.get_conn().cursor() as cur:
            cur.execute("SELECT id, title, body, url FROM documents WHERE id = ANY(%s)", (doc_ids,))
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self):
        self.pool.closeall()


def parse_qrels_file(filepath: str) -> Set[str]:
    """Parse qrels file and extract unique document IDs."""
    doc_ids = set()
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3:
                doc_id = parts[2]  # Format: query_id 0 doc_id relevance
                doc_ids.add(doc_id)
    return doc_ids


def get_collection_doc_ids(qdrant: QdrantClient, collection_name: str) -> Set[str]:
    """Fetch all doc_ids from a Qdrant collection."""
    print(f"🔎 Fetching existing documents from '{collection_name}'...")
    if not qdrant.collection_exists(collection_name):
        print(f"   Collection '{collection_name}' does not exist.")
        return set()

    existing_ids = set()
    next_offset = None
    
    while True:
        records, next_offset = qdrant.scroll(
            collection_name=collection_name,
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
            
    print(f"✅ Found {len(existing_ids):,} documents in '{collection_name}'.")
    return existing_ids


def get_points_by_doc_ids(qdrant: QdrantClient, collection_name: str, doc_ids: List[str]) -> Dict[str, models.PointStruct]:
    """Fetch full points (with vectors) for specific doc_ids from a collection."""
    if not doc_ids:
        return {}
    
    points_map = {}
    
    # Batch the retrieval to avoid timeouts
    batch_size = 100
    for i in range(0, len(doc_ids), batch_size):
        batch_ids = doc_ids[i:i+batch_size]
        
        # Use scroll with filter to get points by doc_id
        for doc_id in batch_ids:
            try:
                results, _ = qdrant.scroll(
                    collection_name=collection_name,
                    scroll_filter=models.Filter(
                        must=[models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id)
                        )]
                    ),
                    with_payload=True,
                    with_vectors=True,
                    limit=1
                )
                if results:
                    points_map[doc_id] = results[0]
            except Exception as e:
                logger.warning(f"Failed to fetch point for doc_id {doc_id}: {e}")
    
    return points_map


def ensure_collection_exists(qdrant: QdrantClient, collection_name: str, vector_size: int):
    """Create collection if it doesn't exist."""
    if not qdrant.collection_exists(collection_name):
        print(f"📦 Creating collection '{collection_name}'...")
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
        )
    
    # Ensure doc_id index exists
    try:
        qdrant.create_payload_index(
            collection_name=collection_name,
            field_name="doc_id",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
    except Exception:
        pass  # Index might already exist


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


def copy_points_to_collection(qdrant: QdrantClient, points: List[models.PointStruct], collection_name: str):
    """Copy points to a target collection in batches."""
    for i in range(0, len(points), QDRANT_UPSERT_BATCH_SIZE):
        batch = points[i:i + QDRANT_UPSERT_BATCH_SIZE]
        max_retries = 5
        for attempt in range(max_retries):
            try:
                qdrant.upsert(collection_name=collection_name, points=batch, wait=True)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Copy upsert failed (Attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"Failed to copy batch to {collection_name} after {max_retries} attempts.")


# ==========================================
# 4. PIPELINE WORKERS (for new embeddings only)
# ==========================================

def embed_worker_with_db(doc_queue: queue.Queue, points_queue: queue.Queue, stats: PipelineStats):
    """Worker that takes docs (with content), creates embeddings, and outputs points."""
    while True:
        item = doc_queue.get()
        if item is None:
            doc_queue.task_done()
            break
        
        docs_batch = item  # List of doc dicts with id, title, body
        
        try:
            texts_to_embed = []
            doc_ids_for_batch = []
            
            # Prepare text content for embedding
            max_chars = int(MAX_TOKENS_PER_DOC * 3.5)  # Approximate char limit
            
            for doc in docs_batch:
                content = (doc.get('title') or "") + "\n\n" + (doc.get('body') or "")
                # Truncate if too long
                if len(content) > max_chars:
                    content = content[:max_chars]
                
                texts_to_embed.append(content)
                doc_ids_for_batch.append(str(doc['id']))
            
            if texts_to_embed:
                start_time = time.time()
                all_embeddings = get_openrouter_embeddings(texts_to_embed)
                duration = time.time() - start_time
                
                if all_embeddings and len(all_embeddings) == len(texts_to_embed):
                    points = []
                    for i, emb in enumerate(all_embeddings):
                        doc_id = doc_ids_for_batch[i]
                        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))
                        payload = {
                            "doc_id": doc_id,
                            "dataset": "qrels"  # Matches old file pattern (uses "dataset" not "source")
                        }
                        points.append(models.PointStruct(id=point_id, vector=emb, payload=payload))
                    
                    points_queue.put((points, len(docs_batch)))
                    stats.update_embed(duration, len(docs_batch))
                else:
                    logger.error(f"Embedding mismatch: {len(all_embeddings) if all_embeddings else 0} vs {len(texts_to_embed)}")
        except Exception as e:
            logger.error(f"Embed worker failed: {e}")
        finally:
            doc_queue.task_done()


def upsert_worker_dual(qdrant: QdrantClient, points_queue: queue.Queue, pbar: tqdm, stats: PipelineStats, doc_queue: queue.Queue):
    """Worker that upserts points to BOTH source and target collections."""
    last_time = time.time()
    
    def do_upsert(collection_name: str, points_batch: List[models.PointStruct]):
        """Upsert a single batch with retries."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                qdrant.upsert(collection_name=collection_name, points=points_batch, wait=True)
                return time.time() - start_time
            except Exception as e:
                error_str = str(e)
                if "payload" in error_str.lower() and "larger than allowed" in error_str.lower():
                    if len(points_batch) <= 1:
                        logger.error(f"Single point too large for Qdrant. Skipping.")
                        return 0
                    logger.warning(f"Qdrant payload too large ({len(points_batch)} points). Splitting...")
                    mid = len(points_batch) // 2
                    t1 = do_upsert(collection_name, points_batch[:mid])
                    t2 = do_upsert(collection_name, points_batch[mid:])
                    return t1 + t2
                
                wait = 2 ** attempt
                logger.warning(f"Upsert to {collection_name} failed (Attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
        
        logger.error(f"Failed to upsert batch to {collection_name} after {max_retries} attempts.")
        return 0
    
    while True:
        try:
            item = points_queue.get(timeout=0.5)
        except queue.Empty:
            pass
        else:
            if item is None:
                points_queue.task_done()
                break
                
            points, num_docs = item
            
            total_duration = 0
            # Upsert to both collections
            for i in range(0, len(points), QDRANT_UPSERT_BATCH_SIZE):
                batch = points[i:i + QDRANT_UPSERT_BATCH_SIZE]
                total_duration += do_upsert(SOURCE_COLLECTION, batch)
                total_duration += do_upsert(TARGET_COLLECTION, batch)
            
            pbar.update(num_docs)
            stats.update_upsert(total_duration, num_docs)
            points_queue.task_done()

        now = time.time()
        dt = now - last_time
        if dt > 0.5:
            f_rate, e_rate, u_rate = stats.get_and_reset_rates(NUM_EMBED_WORKERS)
            
            pbar.set_postfix({
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
    # Initialize database connection
    db = Database(PG_LOCAL_PORT)
    
    qdrant = QdrantClient(
        # host='127.0.0.1', 
        host='10.0.3.2',  # When running on server directly
        port=QDRANT_HTTP_PORT, 
        api_key="DkJsZtSFdDjCClMz2vv5qAJmmrq2Si74", 
        https=False,
        timeout=120
    )

    try:
        # 1. Parse qrels file to get required doc IDs
        script_dir = os.path.dirname(os.path.abspath(__file__))
        qrels_path = os.path.join(script_dir, QRELS_FILE)
        
        print(f"📄 Parsing qrels file: {qrels_path}")
        qrels_doc_ids = parse_qrels_file(qrels_path)
        print(f"   Found {len(qrels_doc_ids):,} unique document IDs in qrels")

        # 2. Prefetch existing doc IDs from source collection
        source_doc_ids = get_collection_doc_ids(qdrant, SOURCE_COLLECTION)
        
        # 3. Get existing doc IDs in target collection (for continuation logic)
        target_doc_ids = get_collection_doc_ids(qdrant, TARGET_COLLECTION)
        
        # 4. Categorize qrels doc IDs
        # - already_in_target: Already processed (in qrels collection)
        # - to_copy: In source but not in target (need to copy)
        # - to_create: Not in source (need to create new embedding)
        already_in_target = qrels_doc_ids & target_doc_ids
        remaining_qrels = qrels_doc_ids - already_in_target
        
        to_copy = remaining_qrels & source_doc_ids
        to_create = remaining_qrels - source_doc_ids
        
        print(f"\n📊 Processing Summary:")
        print(f"   Already in '{TARGET_COLLECTION}': {len(already_in_target):,} (skipping)")
        print(f"   To copy from '{SOURCE_COLLECTION}': {len(to_copy):,}")
        print(f"   To create (new embeddings): {len(to_create):,}")
        
        if not to_copy and not to_create:
            print("🎉 All qrels documents already processed!")
            return

        # 5. Ensure collections exist
        # Get vector size from source collection or create a test embedding
        if qdrant.collection_exists(SOURCE_COLLECTION):
            collection_info = qdrant.get_collection(SOURCE_COLLECTION)
            vector_size = collection_info.config.params.vectors.size
        else:
            print("⚠️  Source collection doesn't exist. Creating test embedding to determine vector size...")
            dummy = get_openrouter_embeddings(["test"])
            if not dummy:
                print("❌ Failed to create test embedding. Exiting.")
                return
            vector_size = len(dummy[0])
        
        ensure_collection_exists(qdrant, SOURCE_COLLECTION, vector_size)
        ensure_collection_exists(qdrant, TARGET_COLLECTION, vector_size)
        
        # 6. Copy existing embeddings from source to target
        if to_copy:
            print(f"\n📋 Copying {len(to_copy):,} embeddings from '{SOURCE_COLLECTION}' to '{TARGET_COLLECTION}'...")
            to_copy_list = list(to_copy)
            
            copy_pbar = tqdm(total=len(to_copy_list), desc="Copying")
            
            for i in range(0, len(to_copy_list), BATCH_SIZE):
                batch_ids = to_copy_list[i:i+BATCH_SIZE]
                
                # Fetch points with vectors from source
                points_map = get_points_by_doc_ids(qdrant, SOURCE_COLLECTION, batch_ids)
                
                if points_map:
                    # Convert to PointStruct for upsert
                    points_to_copy = []
                    for doc_id, record in points_map.items():
                        point = models.PointStruct(
                            id=record.id,
                            vector=record.vector,
                            payload=record.payload
                        )
                        points_to_copy.append(point)
                    
                    copy_points_to_collection(qdrant, points_to_copy, TARGET_COLLECTION)
                
                copy_pbar.update(len(batch_ids))
            
            copy_pbar.close()
            print(f"✅ Copied {len(to_copy):,} embeddings to '{TARGET_COLLECTION}'")

        # 7. Create new embeddings for documents not in source
        if to_create:
            print(f"\n🔧 Creating {len(to_create):,} new embeddings...")
            
            to_create_list = list(to_create)
            
            # Estimate cost by sampling documents from DB
            print("\n--- 💰 COST ESTIMATION ---")
            sample_ids = to_create_list[:min(1000, len(to_create_list))]
            sample_docs = db.get_documents_by_ids(sample_ids)
            
            if sample_docs:
                total_chars = sum(len((d.get('title') or "") + (d.get('body') or "")) for d in sample_docs)
                avg_chars = total_chars / len(sample_docs)
                avg_tokens = avg_chars / 3.5  # Rough token estimate
            else:
                avg_tokens = 1000  # Fallback estimate
            
            total_est_tokens = avg_tokens * len(to_create)
            est_price = (total_est_tokens / 1_000_000) * PRICE_PER_1M_TOKENS
            print(f"Docs to Process: {len(to_create):,}")
            print(f"Avg Tokens/Doc:  {avg_tokens:.0f}")
            print(f"Total Tokens:    {total_est_tokens:,.0f}")
            print(f"Est. Cost:       ${est_price:.4f}")
            print("---------------------------")
            input("Press Enter to start embedding creation (Ctrl+C to cancel)...")
            
        # Initialize queues and stats
        doc_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE * 2)
        points_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        stats = PipelineStats()
        
        # Track skipped documents (not found in DB)
        skipped_docs = [0]
        
        # Producer thread - fetches documents from DB and feeds them in batches
        def producer_with_fetch():
            for i in range(0, len(to_create_list), BATCH_SIZE):
                batch_ids = to_create_list[i:i+BATCH_SIZE]
                
                start_time = time.time()
                docs = db.get_documents_by_ids(batch_ids)
                duration = time.time() - start_time
                
                if docs:
                    doc_queue.put(docs)
                    stats.update_fetch(duration, len(docs))
                    
                    # Track skipped
                    if len(docs) < len(batch_ids):
                        skipped_docs[0] += (len(batch_ids) - len(docs))
                else:
                    logger.warning(f"No documents found for batch starting at {i}")
                    skipped_docs[0] += len(batch_ids)
            
            # Signal end
            for _ in range(NUM_EMBED_WORKERS):
                doc_queue.put(None)
        
        threads = []
        
        # Start producer (fetches from DB)
        t_producer = threading.Thread(target=producer_with_fetch)
        t_producer.start()
        threads.append(t_producer)
        
        # Start embed workers
        for _ in range(NUM_EMBED_WORKERS):
            t_embed = threading.Thread(target=embed_worker_with_db, args=(doc_queue, points_queue, stats))
            t_embed.start()
            threads.append(t_embed)
        
        # Start upsert worker
        pbar = tqdm(total=len(to_create_list), desc="Creating embeddings")
        t_upsert = threading.Thread(target=upsert_worker_dual, args=(qdrant, points_queue, pbar, stats, doc_queue))
        t_upsert.start()
        threads.append(t_upsert)
        
        # Wait for completion
        t_producer.join()
        
        for i in range(NUM_EMBED_WORKERS):
            threads[i+1].join()
        
        points_queue.put(None)
        t_upsert.join()
        
        pbar.close()
        print(f"✅ Created {len(to_create) - skipped_docs[0]:,} new embeddings in both collections")
        if skipped_docs[0] > 0:
            print(f"⚠️  Skipped {skipped_docs[0]:,} documents (not found in PostgreSQL 'documents' table)")

        print("\n🎉 Ingestion Complete!")
        
        # Final stats
        final_target_count = len(get_collection_doc_ids(qdrant, TARGET_COLLECTION))
        final_source_count = len(get_collection_doc_ids(qdrant, SOURCE_COLLECTION))
        print(f"   '{TARGET_COLLECTION}' now has {final_target_count:,} documents")
        print(f"   '{SOURCE_COLLECTION}' now has {final_source_count:,} documents")
    
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