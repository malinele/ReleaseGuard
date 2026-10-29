# ReleaseGuard API Guide

A practical guide to the ReleaseGuard REST API. All examples assume a server at `http://127.0.0.1:8000` and use placeholder values; replace IDs and tokens with your own. Request and response bodies are JSON.

## Interactive docs

The server publishes generated documentation for every endpoint, including request schemas and enum values:

| URL | What it is |
|-----|-----------|
| `http://127.0.0.1:8000/docs` | Swagger UI - try requests from the browser |
| `http://127.0.0.1:8000/redoc` | ReDoc - read-only reference |
| `http://127.0.0.1:8000/openapi.json` | Machine-readable OpenAPI schema |

```bash
curl -s http://127.0.0.1:8000/openapi.json | head -c 300
```

## Authentication

ReleaseGuard has three access modes. Which one applies depends on how the server was started.

### 1. Open local mode (no auth)

With no write token configured and user auth not required, every `/api` route is open. This is the default for local use.

```bash
curl -s http://127.0.0.1:8000/api/projects
```

### 2. Shared token header

If the server has `RELEASEGUARD_WRITE_TOKEN` set, every `/api` request (except `/api/auth/*`) must carry the matching `X-ReleaseGuard-Token` header. A missing or wrong token returns `401`.

```bash
curl -s http://127.0.0.1:8000/api/projects \
  -H "X-ReleaseGuard-Token: <your-shared-token>"
```

### 3. Bearer session (user auth)

When `RELEASEGUARD_REQUIRE_USER_AUTH=true` (or `RELEASEGUARD_ENV=production`), routes require either the shared token above or a user session. Log in with a username and password to get a bearer token: <!-- driftwatch: ignore=env -->

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "<password>"}'
```

Response:

```json
{"access_token": "<token>", "token_type": "bearer", "expires_at": "2026-01-01T12:00:00"}
```

Send the token on later requests:

```bash
curl -s http://127.0.0.1:8000/api/projects \
  -H "Authorization: Bearer <token>"
```

Check who the token belongs to:

```bash
curl -s http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer <token>"
# {"id": 1, "username": "alice", "display_name": null, "is_active": true}
```

Revoke the session:

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/logout \
  -H "Authorization: Bearer <token>"
# {"status": "logged_out"}
```

The first owner account is created out of band with `scripts/create_owner.py`; there is no API endpoint for creating users.

## End-to-end walkthrough

This sequence takes one change from idea to release. IDs in the URLs (`1`) assume a fresh database; use the `id` returned by each response otherwise. In user-auth mode, add `-H "Authorization: Bearer <token>"` to every call.

Optional: send an `actor` header on create/update calls (projects, requirements, proposals) to record who made the change in the audit log. Transitions take `actor` in the body instead.

### 1. Create a project

Required: `name`. Optional: `description`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" \
  -H "actor: alice" \
  -d '{"name": "Payments Portal", "description": "Customer-facing payments app"}'
```

### 2. Create a requirement

Required: `project_id`, `requirement_id` (your own label), `title`. Optional: `description`, `acceptance_criteria`, `priority` (`low`, `medium`, `high`, `critical`; default `medium`), `status` (`active`, `deprecated`, `satisfied`; default `active`).

```bash
curl -s -X POST http://127.0.0.1:8000/api/requirements \
  -H "Content-Type: application/json" \
  -H "actor: alice" \
  -d '{
    "project_id": 1,
    "requirement_id": "REQ-001",
    "title": "Users can export invoices as PDF",
    "description": "Export button on the invoice page",
    "acceptance_criteria": "PDF downloads in under 5 seconds",
    "priority": "high"
  }'
```

### 3. Create a change proposal

Required: `project_id`, `proposal_id` (your own label), `summary`. Optional: `generated_by`, `files_expected` (list of paths), `risk_level` (`low`, `medium`, `high`, `critical`; default `medium`), `rationale`. A new proposal starts in `draft`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/proposals \
  -H "Content-Type: application/json" \
  -H "actor: alice" \
  -d '{
    "project_id": 1,
    "proposal_id": "PROP-001",
    "summary": "Add PDF export for invoices",
    "generated_by": "ai-assistant",
    "files_expected": ["app/invoices/export.py", "tests/test_export.py"],
    "risk_level": "medium",
    "rationale": "Implements REQ-001"
  }'
```

### 4. Link the requirement to the proposal

`requirement_id` here is the numeric database `id` of the requirement (not the `REQ-001` label). The body must also repeat `proposal_id` (numeric), and it must match the URL or the call returns `400`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/proposals/1/requirements \
  -H "Content-Type: application/json" \
  -d '{"proposal_id": 1, "requirement_id": 1}'
```

### 5. Record test evidence

Required: `proposal_id`, `test_type` (`unit`, `integration`, `system`, `manual`, `automated`), `command_or_procedure` (must not be blank), `result` (`passed`, `failed`, `skipped`, `inconclusive`). Optional: `evidence_notes`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/proposals/1/test-evidence \
  -H "Content-Type: application/json" \
  -d '{
    "proposal_id": 1,
    "test_type": "unit",
    "command_or_procedure": "pytest tests/test_export.py -q",
    "result": "passed",
    "evidence_notes": "12 passed"
  }'
```

### 6. Record the security review

Required: `proposal_id`. Optional: `status` (`pending`, `in_progress`, `passed`, `failed`, `waived`; default `pending`), `reviewer`, `notes`, `risk_acceptance_reason`. The release gate accepts `passed`, or `waived` together with a `risk_acceptance_reason`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/proposals/1/security-review \
  -H "Content-Type: application/json" \
  -d '{
    "proposal_id": 1,
    "status": "passed",
    "reviewer": "bob",
    "notes": "No injection or access-control issues found"
  }'
```

### 7. Record the release decision

The `release_ready` transition requires a release decision to exist, so record it before the final transitions. Required: `proposal_id`, `decision` (`approved`, `rejected`, `deferred`, `conditional`). Optional: `decision_maker`, `decision_notes`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/proposals/1/release-decision \
  -H "Content-Type: application/json" \
  -d '{
    "proposal_id": 1,
    "decision": "approved",
    "decision_maker": "carol",
    "decision_notes": "Evidence reviewed"
  }'
```

### 8. Move the proposal through the workflow

`POST /api/proposals/{id}/transition` takes `target_status` and an optional `actor`. The workflow is a strict linear chain; you cannot skip a step:

`draft` -> `context_review` -> `implementation` -> `test_review` -> `security_review` -> `release_ready` -> `released`

Call it once per step, changing `target_status` each time:

```bash
curl -s -X POST http://127.0.0.1:8000/api/proposals/1/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "context_review", "actor": "alice"}'

curl -s -X POST http://127.0.0.1:8000/api/proposals/1/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "implementation", "actor": "alice"}'

curl -s -X POST http://127.0.0.1:8000/api/proposals/1/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "test_review", "actor": "alice"}'

curl -s -X POST http://127.0.0.1:8000/api/proposals/1/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "security_review", "actor": "alice"}'

# Release gates are checked here (see below)
curl -s -X POST http://127.0.0.1:8000/api/proposals/1/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "release_ready", "actor": "carol"}'

curl -s -X POST http://127.0.0.1:8000/api/proposals/1/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "released", "actor": "carol"}'
```

A successful call returns `{"message": "...", "proposal": {...}}`. Moving from `security_review` to `release_ready` is blocked with `400` unless all four gates hold: at least one linked requirement (step 4), at least one test evidence record (step 5), a security review that is `passed` or `waived` with a reason (step 6), and a release decision (step 7). The error `detail` lists each failed gate.

You can also see the overall picture across proposals:

```bash
curl -s http://127.0.0.1:8000/api/release-readiness
```

### 9. Inspect traceability

Everything attached to one proposal - requirements, test evidence, security review, release decision:

```bash
curl -s http://127.0.0.1:8000/api/traceability/proposal/1
```

The whole-system matrix is at `GET /api/traceability`.

### 10. Inspect the audit log

Every create, update and transition above wrote an audit event. Filter with `entity_type`, `entity_id` and `limit` (default 100, max 500):

```bash
curl -s "http://127.0.0.1:8000/api/audit?entity_type=proposal&entity_id=1&limit=50"
```

Fetch one event with `GET /api/audit/{audit_id}`. `GET /api/audit/export` returns an export bundle and also accepts an `actor` filter.

## Searching and filtering

List endpoints accept `skip` (default 0) and `limit` (default 100) for paging.

`q` is a case-insensitive substring search:

- `GET /api/projects?q=` matches project name and description.
- `GET /api/requirements?q=` matches `requirement_id`, title and description.

```bash
curl -s "http://127.0.0.1:8000/api/projects?q=payments"
curl -s "http://127.0.0.1:8000/api/requirements?q=invoice"
```

`project_id` narrows requirements (and proposals) to one project, and combines with `q`:

```bash
curl -s "http://127.0.0.1:8000/api/requirements?project_id=1"
curl -s "http://127.0.0.1:8000/api/requirements?project_id=1&q=pdf"
curl -s "http://127.0.0.1:8000/api/proposals?project_id=1"
```

## Errors

Errors are JSON with a `detail` field: `{"detail": "Proposal not found"}`.

| Status | Meaning |
|--------|---------|
| `400` | The request was understood but rejected by the application: the body `proposal_id` does not match the URL, an invalid workflow transition, or failed release gates. |
| `404` | The resource does not exist (project, requirement, proposal, link, test evidence, security review, release decision, audit event). |
| `401` | You are not authenticated. |
| `403` | You are authenticated but your role is not allowed to do this. |
| `422` | The JSON body failed schema validation: a missing required field, a wrong type, an unknown enum value, or a blank `command_or_procedure`. The response lists each offending field under `detail`. |

### 401 vs 403 under user auth

When user auth is required:

- **401** means ReleaseGuard does not know who you are: no `Authorization` header, an invalid or expired token, a logged-out session, or a wrong `X-ReleaseGuard-Token`. Fix by logging in again.
- **403** means the token is valid but your role lacks the permission for that action, for example a `viewer` or `support` user attempting a proposal write. Logging in again will not help; use an account with a suitable role (owner, admin and finance can write proposals).

```bash
# No credentials -> 401
curl -s -i -X POST http://127.0.0.1:8000/api/proposals \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "proposal_id": "P-2", "summary": "x"}'

# Valid viewer token on a write -> 403
curl -s -i -X POST http://127.0.0.1:8000/api/proposals \
  -H "Authorization: Bearer <viewer-token>" \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "proposal_id": "P-2", "summary": "x"}'
```

### Validation and not-found examples

```bash
# Invalid enum value or missing field
curl -s -i -X POST http://127.0.0.1:8000/api/proposals/1/test-evidence \
  -H "Content-Type: application/json" \
  -d '{"proposal_id": 1, "test_type": "smoke", "command_or_procedure": " ", "result": "passed"}'

# Skipping a workflow step -> 400 "Invalid transition from draft to released"
curl -s -i -X POST http://127.0.0.1:8000/api/proposals/1/transition \
  -H "Content-Type: application/json" \
  -d '{"target_status": "released"}'

# Unknown ID -> 404
curl -s -i http://127.0.0.1:8000/api/proposals/99999
```
