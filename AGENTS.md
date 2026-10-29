# ReleaseGuard – Guide for AI Coding Agents

ReleaseGuard is an audit-ready, local-first FastAPI platform for managing
software delivery, including AI-assisted code. It tracks requirements, change
proposals, workflow gates, test evidence, security reviews, release decisions,
traceability, and an append-only audit history. See `README.md` for setup.

## Before and after every change

Run the full test suite and keep it green:

```bash
.venv/bin/python -m pytest tests/ -q
```

Do not leave failing tests behind. Add or update tests for any behavior you
change.

## Code conventions

- Follow existing patterns before inventing new ones.
- HTTP endpoints are FastAPI routers in `app/api/`, one module per resource.
- Business logic lives in `app/services/`; routers stay thin.
- Every router applies its RBAC dependencies (see `app/rbac.py`); new routes
  must be protected the same way as their neighbors.
- Validate input with the Pydantic schemas in `app/schemas/`.
- Prefer small, focused changes and keep functions and files readable.

## Security

- Never commit secrets, tokens, passwords, or local databases.
- Configuration comes from environment variables (see the README table).
- Do not log or echo secret values.

## Documentation and commits

- Update the relevant file in `docs/` (and `CHANGELOG.md`) when behavior changes.
- Use conventional commit messages: `feat:`, `fix:`, `docs:`, `test:`,
  `refactor:`, `chore:`, `perf:`, `ci:`.
