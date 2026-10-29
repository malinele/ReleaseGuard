# ReleaseGuard

ReleaseGuard is a lightweight FastAPI service for release-readiness workflows. It provides an HTTP API for inspecting release state, protects write operations with a shared token, and includes an automated test suite.

## Overview

The ASGI application is exposed as `app.main:app` and can be run with Uvicorn. Read-only operations can be used to discover and inspect release information, while state-changing operations require the `RELEASEGUARD_WRITE_TOKEN` secret.

FastAPI provides interactive OpenAPI documentation while the service is running:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

Use the generated API documentation to see the available routes, request schemas, and authentication fields exposed by the current application version.

## Features

- FastAPI application with automatic request validation and OpenAPI documentation.
- Token-protected write operations for securing state-changing requests.
- Clear separation between local development and production Uvicorn startup.
- Configuration through environment variables rather than committed secrets.
- Automated tests covering the application behavior.

## Quickstart

Create and activate a virtual environment, then install the pinned dependencies from `requirements.txt`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Set a strong write token before starting the service:

```bash
export RELEASEGUARD_WRITE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Start the development server with automatic reload:

```bash
uvicorn app.main:app --reload
```

The server listens on `http://127.0.0.1:8000` by default. Open `/docs` to explore the API and determine how the write token must be supplied to protected endpoints.

For a production-style process, disable reload and bind the server explicitly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Running tests

Run the test suite from the repository root so that application imports resolve correctly:

```bash
python -m pytest
```

For more concise output, use:

```bash
python -m pytest -q
```

Run tests after changing application code, configuration handling, or API behavior. Do not use a production write token in local test runs.

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `RELEASEGUARD_WRITE_TOKEN` | For protected writes | Shared secret used to authorize state-changing API requests. Set it before starting the service and rotate it by updating the environment and restarting the process. |
| `RELEASEGUARD_ENV` | No | `prod`/`production` enables fail-closed production mode. |
| `RELEASEGUARD_REQUIRE_USER_AUTH` | No | `true` requires user-session auth outside production mode. |
| `RELEASEGUARD_CSRF_SECRET` | Recommended in production | Signing secret for UI CSRF tokens. |
| `RELEASEGUARD_OWNER_PASSWORD` | For `create_owner.py` | Password for the bootstrap owner user. |
| `DATABASE_URL` | No | SQLAlchemy URL, default `sqlite:///./releaseguard.db`. |

Keep `RELEASEGUARD_WRITE_TOKEN` out of source control, logs, screenshots, and CI output. Use a separate secret in each deployed environment and provide it through the environment or the platform's secret manager.

The host and port are Uvicorn settings rather than application secrets. They can be selected with command-line options:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Production mode and user accounts

Set `RELEASEGUARD_ENV=production` (or `prod`) to run fail-closed: protected API and UI routes then require a valid user session or the shared write token. When unset, local-dev behavior applies. `RELEASEGUARD_REQUIRE_USER_AUTH=true` enables user-session auth without production mode. Set `RELEASEGUARD_CSRF_SECRET` explicitly in production; it otherwise falls back to the write token and then to a local-dev default.

Create the first owner user with the bootstrap script. The password is read only from the environment, and the script refuses to run if an owner already exists:

```bash
RELEASEGUARD_OWNER_PASSWORD='choose-a-strong-password' python scripts/create_owner.py --username owner
```

## Seed data

To load a demo project with one complete release lifecycle (requirements, proposal, test evidence, security review, release decision), run from the repository root:

```bash
python seed_data.py
```

The database defaults to `sqlite:///./releaseguard.db` and can be changed with `DATABASE_URL`.

## Project structure

- `app/main.py` defines the ASGI application imported as `app.main:app`.
- `scripts/create_owner.py` bootstraps the first owner user.
- `seed_data.py` loads demo data.
- `app/` contains the application package and supporting implementation modules.
- `tests/` contains the automated test suite.
- `AGENTS.md` contains repository-specific contributor guidance.
- `README.md` documents installation, operation, testing, and configuration.

## Troubleshooting

### Dependency and install problems

Install from the pinned `requirements.txt` inside a fresh virtual environment. A stale environment is the most common cause of import errors; if in doubt, recreate `.venv` and reinstall.

- **`RuntimeError: Form data requires "python-multipart" to be installed`** (or a similar error when a route accepts form data): `python-multipart` is missing. Run `python -m pip install -r requirements.txt`; the file pins `python-multipart==0.0.9`.
- **`ModuleNotFoundError: No module named 'jinja2'`** when the server-rendered UI pages load: `jinja2` is missing. Reinstall from `requirements.txt`, which pins `jinja2==3.1.3`.
- **Async tests fail, are skipped, or report event-loop errors**: `pytest-asyncio` must be installed at a version compatible with the pinned `pytest`. `requirements.txt` pins `pytest==8.0.0` with `pytest-asyncio==0.23.8`; the earlier `0.23.3` pin was a broken combination. Do not downgrade `pytest-asyncio` independently, and reinstall from `requirements.txt` if versions have drifted.

### Running the service

- **`uvicorn: command not found`**: activate the virtual environment, or run `python -m uvicorn app.main:app --reload`.
- **`ModuleNotFoundError: No module named 'app'`**: run `uvicorn` and `pytest` from the repository root.
- **`Address already in use`**: another process holds port 8000. Stop it or choose another port with `--port`.
- **Write requests are rejected (401/403)**: confirm `RELEASEGUARD_WRITE_TOKEN` is exported in the same shell that started the server, and that the server was restarted after the value changed. Check `/docs` for how the token is supplied.

### Tests

- Run `python -m pytest -q` from the repository root. If failures mention missing packages, see the dependency section above before changing any code.

## Documentation

- [User guide](docs/user-guide.md) – day-to-day usage of the web UI and release workflow.
- [Administrator guide](docs/admin-guide.md) – deployment, configuration, user management, and operations.
- [API guide](docs/api-guide.md) – practical REST API reference with an end-to-end curl walkthrough.
- [Architecture overview](docs/architecture.md) – system design, data model, and workflow state machine.
- [Changelog](CHANGELOG.md) – notable changes for each release.

## License

ReleaseGuard is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE).
For commercial use, see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
