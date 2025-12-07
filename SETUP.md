# Local Development Setup

## Quick Start

```bash
# 1. Install Git LFS and pull large files
brew install git-lfs && git lfs install && git lfs pull

# 2. Initialize storage and start Docker services (~5 min)
./scripts/setup.sh

# 3. Install dependencies
poetry install
cd backend/api && poetry install && cd ../..
cd backend/eval && poetry install && cd ../..
cd frontend && npm install && cd ..

# 4. Setup environment files
cp backend/api/.env.example backend/api/.env
cp backend/eval/.env.example backend/eval/.env

# 5. Start backend (Terminal 1)
npm run backend:dev

# 6. Start frontend (Terminal 2)
cd frontend && npm run dev
```

## What's Included

Pre-built storage backups contain:
- **PostgreSQL**: 1.6M MS MARCO documents with metadata 
- **Solr**: 1.6M MS MARCO documents, BM25 indexed 
- **Qdrant**: Vector embeddings with Qwen/Qwen3-Embedding-0.6B 

## Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Solr: http://localhost:8983/solr/
- Qdrant: http://localhost:6333/dashboard

## Run Indexing (Optional)

If you need to rebuild indexes from scratch:

### Solr (BM25 Lexical Search)
```bash
# Import dataset to PostgreSQL (~45-60 min)
cd scripts && poetry run python dataset2postgres.py && cd ..

# Index documents in Solr (~8-10 min)
poetry run python backend/search/index_pipeline.py --dataset "MS MARCO" --core small --batch-size 3000
```

### Qdrant (Vector Embeddings)
```bash
# Local embedding generation (500h+ on CPU, requires GPU recommended)
cd backend/embeddings && pipenv install
pipenv run python ingest.py --dataset "MS MARCO" --batch-size 100

# OR remote via OpenRouter ($250 for full dataset, requires API key in .env)
pipenv run python embedding_ingestion_openrouter.py --dataset "MS MARCO" --batch-size 100
```

## Run Evaluations

```bash
# Download TREC evaluation assets (first time only)
bash scripts/pull_qrels.sh

# Run evaluation
cd backend/eval && poetry run eval-cli run trec-dl-23
```


