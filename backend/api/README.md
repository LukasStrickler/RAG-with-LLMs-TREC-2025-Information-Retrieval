# Backend API Service

This directory contains the FastAPI service responsible for the Retrieval Augmented Generation (RAG) pipeline. It handles document retrieval using lexical (Solr), vector (Qdrant), and hybrid strategies, and serves document details.

## Features

-   **Retrieval Endpoint**: `/api/v1/retrieve` supports Lexical, Vector, and Hybrid search.
-   **Document Details**: `/api/v1/document/{id}` fetches full document content.
-   **Metadata**: `/api/v1/metadata` provides dataset and index information.
-   **Ollama Integration**: Uses `qwen3-embedding:0.6b` for generating query embeddings on the fly.
-   **SSH Tunneling**: Automatically establishes secure tunnels to remote Solr, Qdrant, and PostgreSQL instances.

## Prerequisites

-   **Python 3.10+**
-   **Poetry**: Dependency management.
-   **Ollama**: For local embedding generation.
    -   Model: `qwen3-embedding:0.6b`

## Installation

1.  **Install Dependencies**:
    You can install dependencies for the entire monorepo or just this service.
    ```bash
    # From root
    npm run update-all
    
    # OR from backend/api
    poetry install
    ```

2.  **Setup Ollama**:
    Ensure Ollama is installed and running, then pull the required embedding model:
    ```bash
    ollama serve
    ollama pull qwen3-embedding:0.6b
    ```

## Configuration

The service requires environment variables to be set in a `.env` file in this directory (`backend/api/.env`).

1.  Copy the example file:
    ```bash
    cp .env.example .env
    ```

2.  Configure the following variables (ask team for credentials):
    -   `API_KEY`: Secret key for authentication (required for `X-API-Key` header).
    -   `SSH_HOST`, `SSH_USER`, `SSH_KEY_PATH`: For tunneling to data services.
    -   `DB_PASSWORD`: For PostgreSQL access.
    -   `QDRANT_API_KEY`: For vector database access.

## Running the Service

### Development
Starts the server with auto-reload enabled.
```bash
# From root
npm run backend:dev

# OR from backend/api
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Production
```bash
# From root
npm run backend
```

The API will be available at `http://localhost:8001`.
Interactive documentation is available at `http://localhost:8001/docs`.

## API Usage

### Retrieval
**POST** `/api/v1/retrieve`
```json
{
  "queries": [
    {
      "query_id": "q1",
      "query_text": "example query",
      "top_k": 10
    }
  ],
  "mode": "hybrid"
}
```

### Document Details
**GET** `/api/v1/document/{doc_id}`
Returns the full content and metadata for a specific document.
