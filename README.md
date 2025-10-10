# RAG with LLMs: TREC 2025 Information Retrieval

> Collaborative research project preparing a Retrieval Augmented Generation (RAG) system for the TREC 2025 Information Retrieval track.

## Project Goals
- Deliver a reproducible RAG pipeline that can be benchmarked with official TREC tooling.
- Explore embedding options (self-hosted vs. managed) and ensure safe, auditable ingestion runs.
- Provide an optional frontend experience for demoing retrieval and generation capabilities.

## Project Snapshot
- Monorepo with clearly separated services for API, embeddings, evaluation, and frontend.
- Backend built with FastAPI and LangChain/LangGraph integrations.
- Embeddings ingestion via dedicated CLI workers (`poetry run embeddings-seed`).
- Database with embeddings for retrieval.
- Frontend prototypes powered by Deno, Next.js, shadcn/ui, and Convex.

## Repository Layout
```text
/                                  
├─ backend/                        # Python backend 
│  ├─ api/                         # FastAPI service + DB access layer
│  ├─ embeddings/                  # ingestion, chunking, vectorization jobs
│  └─ eval/                        # TREC evaluation scripts and configs
├─ frontend/                       # Deno + Next.js application
└─ .docs/                          # setup guides, meetings, research notes
```

## Getting Started
### Prerequisites
- Poetry (https://python-poetry.org/docs/#installation)
- Deno runtime (https://docs.deno.com/runtime/getting_started/installation/)
- Access to project environment variables (`backend/.env`, `frontend/.env`)

### Quickstart
1. Copy environment templates: `cp backend/.env.example backend/.env` and `cp frontend/.env.example frontend/.env`.
2. Install backend environments:
   ```bash
   cd backend/api && poetry install
   cd ../embeddings && poetry install
   cd ../eval && poetry install
   ```
3. Install frontend dependencies:
   ```bash
   cd frontend
   deno install
   ```
4. For detailed instructions, refer to [`.docs/setup.md`](.docs/setup.md).


## Team
- Lean Fürst — [lean.henriques.fuerst@students.uni-mannheim.de](mailto:lean.henriques.fuerst@students.uni-mannheim.de)
- Johannes Kramberg — [johannes.kramberg@students.uni-mannheim.de](mailto:johannes.kramberg@students.uni-mannheim.de)
- Lukas Strickler — [lukas.strickler@students.uni-mannheim.de](mailto:lukas.strickler@students.uni-mannheim.de)
- Yonis Teubner — [yonis.teubner@students.uni-mannheim.de](mailto:yonis.teubner@students.uni-mannheim.de)
- Dan Thösen — [dan.thoesen@students.uni-mannheim.de](mailto:dan.thoesen@students.uni-mannheim.de)
- Niklas Wichter — [niklas.wichter@students.uni-mannheim.de](mailto:niklas.wichter@students.uni-mannheim.de)

## License
Released under the MIT License. See [`LICENSE.md`](LICENSE.md) for details.
