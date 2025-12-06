"""Dataset-aware indexing pipeline: PostgreSQL to Solr."""
import argparse
import sys
from typing import Optional
from tqdm import tqdm
from db import Database
from solr import SolrIndexer


# Configuration password is non critical since the db is never publicly reachable - hardcoded for simplicity
# For a local setup change as needed
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5433,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'password',
    'sslmode': 'disable'
}

SOLR_URL = 'http://localhost:8983/solr'


def list_datasets(db: Database):
    """Display available datasets."""
    datasets = db.get_datasets()
    print("\n" + "=" * 80)
    print("Available Datasets")
    print("=" * 80)
    for ds in datasets:
        print(f"\nDataset: {ds['name']}")
        print(f"  ID: {ds['id']}")
        print(f"  Version: {ds['version']} | Split: {ds['split']}")
        print(f"  Documents: {ds['doc_count']:,}")


def index_dataset(db: Database, dataset_name: str, core: str, limit: Optional[int], batch_size: int, clear: bool):
    """Index a dataset into Solr."""
    
    # Get dataset
    dataset = db.get_dataset_by_name(dataset_name)
    if not dataset:
        print(f"Error: Dataset '{dataset_name}' not found")
        return
    
    indexer = SolrIndexer(SOLR_URL, core)
    
    # Clear core if requested
    if clear:
        current_count = indexer.count()
        if current_count > 0:
            print(f"\nClearing {current_count:,} existing documents from '{core}' core...")
            if indexer.delete_all():
                print(f"Cleared successfully")
            else:
                print("Failed to clear - continuing anyway...")
    
    print(f"\n{'=' * 80}")
    print(f"Indexing: {dataset['name']} -> Solr core '{core}'")
    print(f"{'=' * 80}")
    print(f"Total docs: {dataset['doc_count']:,} | Limit: {limit or 'None'} | Batch: {batch_size}")
    
    # Step 1: Get document IDs
    print(f"\n[1/3] Fetching document IDs...")
    doc_ids = db.get_document_ids(dataset['id'], limit)
    print(f"Found {len(doc_ids):,} document IDs")
    
    if not doc_ids:
        print("No documents to index")
        return
    
    # Step 2: Load documents
    print(f"\n[2/3] Loading documents from database...")
    documents = []
    with tqdm(total=len(doc_ids), desc="Loading", unit="docs") as pbar:
        for i in range(0, len(doc_ids), 1000):
            batch = doc_ids[i:i + 1000]
            documents.extend(db.get_documents(batch))
            pbar.update(len(batch))
    
    print(f"Loaded {len(documents):,} documents")
    if len(documents) != len(doc_ids):
        print(f"Warning: {len(doc_ids) - len(documents):,} docs not found in documents table")
    
    # Step 3: Index to Solr
    print(f"\n[3/3] Indexing to Solr...")
    indexed = indexer.index(documents, batch_size)
    total = indexer.count()
    
    print(f"\n{'=' * 80}")
    print(f"Complete: {indexed:,} docs indexed | Total in '{core}': {total:,}")
    print(f"{'=' * 80}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Index PostgreSQL datasets into Solr')
    parser.add_argument('--list-datasets', action='store_true', help='List available datasets')
    parser.add_argument('--dataset', type=str, help='Dataset name to index')
    parser.add_argument('--core', type=str, choices=['small', 'medium', 'big'], help='Solr core')
    parser.add_argument('--limit', type=int, help='Limit number of documents')
    parser.add_argument('--batch-size', type=int, default=500, help='Batch size (default: 500)')
    parser.add_argument('--clear', action='store_true', help='Clear existing documents in core before indexing')
    
    args = parser.parse_args()
    
    # Connect to database
    try:
        db = Database(DB_CONFIG)
        print(f"Connected to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)
    
    try:
        if args.list_datasets:
            list_datasets(db)
        elif args.dataset and args.core:
            index_dataset(db, args.dataset, args.core, args.limit, args.batch_size, args.clear)
        else:
            parser.print_help()
            print("\nError: Use --list-datasets OR specify both --dataset and --core")
    finally:
        db.close()
        print("\nDatabase connection closed")


if __name__ == "__main__":
    main()
