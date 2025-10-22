# Project Documentation

This directory collects the living documentation for the TREC 2025 Retrieval project. Use the sections below as an index when you need onboarding help, API references, or architecture notes.

## Quick Links
- [**Setup Guide**](setup.md) – end-to-end bootstrap instructions (`npm run update-all`, Poetry, Deno, CodeRabbit).
- [**API Reference**](api.md) – FastAPI surface, auth requirements, and local development tips.
- [**Coding Conventions**](coding-conventions.md) – naming rules, formatting expectations, and reviewer checklist.
- [**Task Tracker**](TASK.md) – current milestone items and status.
- [**KPIs**](KPI.md) – evaluation targets and metric definitions.
- [**Meeting Notes**](meetings/) – summaries and decisions captured per sync.

## Architecture & Data Models
- [**UML Overview**](uml/README.md) explains how we generate diagrams from the shared Pydantic models.
- [`uml/classes.puml`](uml/classes.puml) – curated specification.
- [`uml/generated_classes.puml`](uml/generated_classes.puml) – auto-generated snapshot (`npm run docs:uml`).
- [`uml/components.puml`](uml/components.puml) & [`uml/sequence_e2e.puml`](uml/sequence_e2e.puml) – component and flow diagrams kept in sync with the code.

## Interactive API Docs
- Start the API with `npm run backend:dev`, then open:
  - Swagger UI: <http://localhost:8000/docs>
  - ReDoc: <http://localhost:8000/redoc>
  - OpenAPI JSON: <http://localhost:8000/openapi.json>
- All protected endpoints expect `X-API-Key` (see `backend/api/.env.example`).
- Available routes today:
  - `GET /health` – service heartbeat.
  - `POST /api/v1/metadata` – dataset/index metadata (currently served from placeholders until the DB lands).
  - `POST /api/v1/retrieve` – retrieval mock returning representative payloads for contract testing.

## Directory Layout

```text
.docs/
├── README.md              # Documentation index (this file)
├── api.md                 # FastAPI usage guide
├── coding-conventions.md  # Style, lint, and review rules
├── KPI.md                 # Metrics reference
├── setup.md               # Environment bootstrap
├── TASK.md                # Task board
├── meetings/              # Meeting notes (dated markdown files)
└── uml/                   # UML specs + generated diagrams
    ├── README.md
    ├── classes.puml
    ├── components.puml
    ├── generated_classes.puml
    └── sequence_e2e.puml
```
