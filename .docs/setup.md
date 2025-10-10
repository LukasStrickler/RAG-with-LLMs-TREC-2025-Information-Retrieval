# Project Setup

Run this from the repository root to copy environment files and install all dependencies in one go:

```bash
npm run update-all
```

> Tip: Rerun `npm run update-all` after changing backend or frontend dependencies.

### Linting & Formatting Quick Reference

- **All services**: `npm run lint` / `npm run format`
- Backend services
  - Lint: `npm run lint:backend` (or per service `npm run lint:backend:api`, etc.)
  - Format: `npm run format:backend`
  - Tools: `ruff`, `black` (via `poetry run`)
- Frontend
  - Lint: `npm run lint:frontend`
  - Format: `npm run format:frontend`
  - Tools: `deno lint`, `deno fmt`

### Environment Files

- Templates live next to each service (`backend/*/.env.example`, `frontend/.env.example`).
- `npm run update-all` copies templates to `.env` if missing.
- The script warns when keys are missing—update `.env` to align with the template.

For broader guidance on naming patterns and lint rules, see [`./coding-conventions.md`](./coding-conventions.md).


## Backend (Python + Poetry)

1. Install Poetry: follow https://python-poetry.org/docs/#installation
2. Enable virtualenvs in-project (optional, consistent across machines):
   ```bash
   poetry config virtualenvs.in-project true
   ```
3. Bootstrap services:
   ```bash
   cd backend/api
   poetry install --no-root
   cd ../embeddings
   poetry install --no-root
   cd ../eval
   poetry install --no-root
   ```
4. Activate an env when working on a component:
   ```bash
   cd backend/api
   poetry shell
   ```

## Frontend (Deno)

1. Install Deno: follow https://docs.deno.com/runtime/getting_started/installation/
2. Install frontend placeholder dependency:
   ```bash
   cd frontend
   deno install
   ```
