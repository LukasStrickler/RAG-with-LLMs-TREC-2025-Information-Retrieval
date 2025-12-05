# Environment Configuration

This directory contains scripts for embedding ingestion that require sensitive credentials. All credentials are now managed through environment variables.

## Setup

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Fill in your credentials in `.env`:**
   - `OPENROUTER_API_KEY`: Your OpenRouter API key
   - `SSH_PASSWORD`: SSH password for remote server access
   - `PG_PASS`: PostgreSQL database password
   - `QDRANT_API_KEY`: Qdrant vector database API key
   - Other SSH credentials as needed

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   or
   ```bash
   pipenv install
   ```

## Security Notes

- **Never commit the `.env` file** - it's already in `.gitignore`
- The `.env.example` file contains placeholder values and is safe to commit
- Keep your API keys and passwords secure
- Rotate credentials regularly

## Environment Variables

### OpenRouter Configuration
- `OPENROUTER_API_KEY`: API key for OpenRouter embeddings service
- `OPENROUTER_URL`: API endpoint (default: https://openrouter.ai/api/v1/embeddings)
- `EMBEDDING_MODEL`: Model to use (default: qwen/qwen3-embedding-8b)
- `PRICE_PER_1M_TOKENS`: Cost per 1M tokens (default: 0.05)

### SSH Configuration
- `SSH_USE`: Enable SSH tunnel (true/false, default: false)
- `SSH_HOST`: SSH server hostname
- `SSH_USER`: SSH username
- `SSH_PASSWORD`: SSH password

### Database Configuration
- `PG_DB`: PostgreSQL database name (default: postgres)
- `PG_USER`: PostgreSQL username (default: postgres)
- `PG_PASS`: PostgreSQL password
- `DB_HOST`: Database host (default: 127.0.0.1)
- `DB_PORT`: Database port (default: 5433)
- `DB_SSLMODE`: SSL mode (default: disable)

### Qdrant Configuration
- `QDRANT_HOST`: Qdrant host (default: 127.0.0.1)
- `QDRANT_PORT`: Qdrant port (default: 6333)
- `QDRANT_HTTP_PORT`: Qdrant HTTP port (default: 6333)
- `QDRANT_GRPC_PORT`: Qdrant GRPC port (default: 6334)
- `QDRANT_API_KEY`: Qdrant API key

### Pipeline Configuration
- `BATCH_SIZE`: Documents per batch (default: 200)
- `MAX_TOKENS_PER_DOC`: Maximum tokens per document (default: 30000)
- `MAX_QUEUE_SIZE`: Queue backpressure limit (default: 20)
- `NUM_EMBED_WORKERS`: Number of embedding worker threads (default: 15)
- `QDRANT_UPSERT_BATCH_SIZE`: Points per Qdrant upsert (default: 300)

## Usage

After configuring your `.env` file, you can run the ingestion scripts:

```bash
# Run the main ingestion script
python ingest.py --dataset small

# Run the OpenRouter ingestion script
python embedding_ingestion_openrouter.py

# Run the Jupyter notebook
jupyter notebook embedding_ingestion.ipynb
```
