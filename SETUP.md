# Local Development Setup

## One-Time Setup

```bash
# Install Git LFS and download dataset
brew install git-lfs && git lfs install && git lfs pull

# Install dependencies
poetry install && cd backend/api && poetry install && cd ../.. && cd frontend && npm install && cd ..
```

## Start Services

```bash
# Start Docker (PostgreSQL, Solr, Qdrant)
docker-compose up -d

# Import dataset (~45-60 min)
cd scripts && poetry run python dataset2postgres.py && cd ..

# Index for search (~8-10 min)
poetry run python backend/search/index_pipeline.py --dataset "MS MARCO" --core small --batch-size 3000

# Start backend (Terminal 1)
npm run backend:dev

# Start frontend (Terminal 2)
npm run dev
```

## Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Solr: http://localhost:8983
- Qdrant: http://localhost:6333/dashboard

## Optional: Vector Search

```bash
# Generate embeddings (500h+ on m4pro) hours on CPU)
cd backend/embeddings && pipenv install && pipenv run python ingest.py --dataset "MS MARCO" --batch-size 100

# Install Ollama for query embeddings
curl -fsSL https://ollama.com/install.sh | sh && ollama pull qwen3-embedding:8b
```

## Troubleshooting

```bash
# Restart Docker
docker-compose down && docker-compose up -d

# Resume import (auto-resumes from checkpoint)
cd scripts && poetry run python dataset2postgres.py

# Verify database
docker exec -it rag-with-llms-trec-2025-information-retrieval-postgres-1 psql -U postgres -d rag_db -c "SELECT COUNT(*) FROM documents;"
```

## Troubleshooting

### Docker Services Not Starting

```bash
# Stop and remove all containers and volumes
docker-compose down -v

# Restart fresh
docker-compose up -d
```

### Dataset Import Fails

Check PostgreSQL is running:
```bash
docker logs postgres
```

Resume import (script automatically resumes from last checkpoint):
```bash
cd scripts
poetry run python dataset2postgres.py
```

### Solr Indexing Fails

Check Solr is running:
```bash
docker logs solr-multiple-cores
curl http://localhost:8983/solr/admin/cores?action=STATUS
```


