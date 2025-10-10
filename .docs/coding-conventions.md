# Coding Conventions

This project enforces consistent code style and structure across services. Follow the guidelines below and leverage the automated lint/format tools to keep changes compliant.

## General Principles

- Aim for clear, descriptive naming (snake_case for Python functions/variables, PascalCase for Python classes, camelCase for JavaScript/TypeScript).
- Prefer explicit imports and avoid wildcard imports.
- Keep functions small and focused; extract helpers when logic grows beyond ~30 lines.
- Document non-obvious decisions inline with concise comments.

## Python Backend (Poetry services)

- Formatting: [`black`](https://black.readthedocs.io/) with line length 88 (`poetry run black .`).
- Linting: [`ruff`](https://docs.astral.sh/ruff/) with rules `E`, `F`, `B`, `I`, `UP`, `SIM` (`poetry run ruff check .`).
- Type hints are encouraged; use `typing`/`pydantic` as needed.
- Tests: `pytest` is available via `poetry run pytest`.

### Module Layout

- Place shared utilities in future `backend/common/` modules (to be added).
- Separate API routers, models, services, and dependencies into distinct packages once implemented.

## Frontend (Deno)

- Formatting: `deno fmt` with default configuration.
- Linting: `deno lint` (add `// deno-lint-ignore` sparingly).
- Use ES modules and avoid default exports when reasonable.
- Environment variables exposed to the browser should be prefixed with `NEXT_PUBLIC_`.

## Commit Hygiene

- Run `npm run update-all` after pulling new dependencies or modifying env templates.
- Run `npm run lint` before opening a PR.
- Use conventional commit format: `<type>(<scope>): <description>`
  - Examples: `feat(api): add retrieval endpoint`, `fix(embeddings): correct vector dimension`
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Future Additions

- Extend this document as modules grow (e.g., database schemas, evaluation workflows).
- Consider adopting additional tooling (e.g., pre-commit hooks) once the codebase stabilizes.

