# Search Indexing Pipeline

Clean, modular indexing pipeline: PostgreSQL to Solr

## Architecture

- **db.py** - Database operations (73 lines)
- **solr.py** - Solr indexing (67 lines)  
- **index_pipeline.py** - Main CLI (118 lines)

## How It Works

1. Reads datasets from dataset table
2. Fetches document IDs from document_in_dataset table
3. Resolves full documents from documents table
4. Indexes to Solr in batches with progress tracking

## Setup

```bash
# Install dependencies from the root directory
cd ../.. && poetry install
ssh -L 5433:10.0.1.7:5432 yonis@95.216.74.52 #postgres portforwarding
ssh -L 5433:i40cc0wsgs0ow0k0o8scw008:5432 yonis@95.216.74.52 #sorl portforawarding
```

## Usage

List datasets:
```bash
poetry run python backend/search/index_pipeline.py --list-datasets
```

Index documents:
```bash
poetry run python index_pipeline.py --dataset small --core big --limit 1000 --clear 
poetry run python index_pipeline.py --dataset small --core big
```

## Performance

- Loading: ~1000 docs/sec from PostgreSQL
- Indexing: ~100 docs/sec to Solr  
- Full dataset (1.6M -- small): ~70 minutes
- Code still not parralellized and and step by step 
Dataset: small (v2.1, 1,612,975 documents)
