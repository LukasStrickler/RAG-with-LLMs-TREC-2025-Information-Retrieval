# API Documentation

## Local Development

```bash
npm run backend:dev
```

Make sure the shared types package is installed (`npm run update-all` or `cd shared && poetry install`) before launching the API.

The command above launches FastAPI with auto-reload. Once running, the interactive docs are available at:
- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

## Authentication

All protected endpoints expect an `X-API-Key` header. To configure it locally:
1. Copy `backend/api/.env.example` to `backend/api/.env`.
2. Set `API_KEY` in the new file (the value can be any strong secret in dev).
3. In Swagger UI click **Authorize**, enter the same key, and confirm.

## Routes (current state)

| Method | Path | Description | Notes |
| --- | --- | --- | --- |
| `GET` | `/health` | Heartbeat and version info | Public endpoint (no auth required). |
| `GET` | `/api/v1/metadata` | Returns dataset, chunking, and index metadata | Served from placeholders until the metadata DB is in place. |
| `POST` | `/api/v1/retrieve` | Retrieval contract returning ranked segments | Connected to Solr (lexical) and Qdrant (vector) via SSH tunnel. |

## Hybrid Retrieval & SSH Tunnel

The retrieval service uses an SSH tunnel to connect to remote Solr and Qdrant instances.
You must configure the SSH credentials in `backend/api/.env` for the service to start correctly.
See `setup.md` for configuration details.

## Useful Commands

| Command | Purpose |
| --- | --- |
| `npm run backend:dev` | FastAPI with reload (recommended while iterating). |
| `npm run backend` | FastAPI without reload (parity with production settings). |
| `npm run docs:uml` | Regenerate UML diagrams from shared Pydantic models. |

## Environment Variables

- Primary configuration lives in `backend/api/.env` (template: `.env.example`).
- Database credentials are commented out for now; they will be activated when the metadata store is delivered.

## Retrieval Process

The retrieval system supports three modes, configurable via the `mode` parameter in the request:

### 1. Lexical Search (Solr)
-   **Engine**: Apache Solr (via SSH tunnel).
-   **Method**: BM25 ranking on `title` and `body` fields.
-   **Query Parser**: eDisMax.
-   **Use Case**: Exact keyword matching, phrase queries.

### 2. Vector Search (Qdrant)
-   **Engine**: Qdrant (via SSH tunnel).
-   **Embedding Model**: `qwen3-embedding:0.6b` (running locally via Ollama).
    -   **Dimension**: 1024.
    -   **Process**: The API generates an embedding for the `query_text` on the fly and queries the Qdrant collection.
-   **Use Case**: Semantic similarity, finding relevant documents that may not share exact keywords.

### 3. Hybrid Search (Fusion)
-   **Method**: Reciprocal Rank Fusion (RRF).
-   **Process**:
    1.  Executes Lexical Search (top 2*k).
    2.  Executes Vector Search (top 2*k).
    3.  Combines results using RRF: `score = 1 / (k + rank)`.
    4.  Re-ranks and returns the top `k` unique documents.
-   **Use Case**: Best of both worlds; robust performance across different query types.

### Document Details
After retrieval (which returns metadata and snippets), the full document content is fetched from the PostgreSQL database using the document ID. This ensures that the user always sees the most complete and up-to-date content.
