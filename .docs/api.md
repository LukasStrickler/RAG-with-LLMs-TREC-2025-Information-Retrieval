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
| `POST` | `/api/v1/retrieve` | Retrieval contract returning mock segments | TODO: wire to real retrieval service + indexes. |

## Useful Commands

| Command | Purpose |
| --- | --- |
| `npm run backend:dev` | FastAPI with reload (recommended while iterating). |
| `npm run backend` | FastAPI without reload (parity with production settings). |
| `npm run docs:uml` | Regenerate UML diagrams from shared Pydantic models. |

## Environment Variables

- Primary configuration lives in `backend/api/.env` (template: `.env.example`).
- Database credentials are commented out for now; they will be activated when the metadata store is delivered.
