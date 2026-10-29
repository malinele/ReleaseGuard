# ReleaseGuard Architecture

This document describes how ReleaseGuard is built, as implemented in the code under `app/`.

## Overview

ReleaseGuard is a FastAPI application (`app/main.py`) backed by SQLAlchemy (`app/database.py`). It serves two surfaces from one process:

- A JSON REST API under `/api` (routers in `app/api/`).
- A server-rendered HTML UI using Jinja2 templates (`app/ui/routes.py`, `app/ui/templates/`).

Storage is a single SQLite file. The default URL is `sqlite:///./releaseguard.db` (`app/config.py`, overridable through the `database_url` setting or a `.env` file). The design is local-first and single-machine: there is no external queue, cache, or mail service. Notifications are written to a local outbox (`app/services/notification_service.py`). The `/health` endpoint returns the status and version. The module-level `uvicorn.run` in `app/main.py` binds to `0.0.0.0:8000`.

Startup runs `init_db()` from the FastAPI lifespan hook. Every response gets `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: same-origin` from `_SecurityHeadersMiddleware`.

## Layers

```
models (app/models)  ->  services (app/services)  ->  API routers (app/api)
                                                  ->  UI routes   (app/ui/routes.py)
```

- **Models** (`app/models/`): SQLAlchemy declarative classes on the shared `Base` from `app/database.py`. Status and type fields are Python `enum` classes stored as SQLAlchemy `Enum` columns.
- **Services** (`app/services/`): static-method classes (`ProjectService`, `RequirementService`, `ProposalService`, `WorkflowService`, `AuditService`, `UserService`, `SessionService`, and others) that hold business logic and take a `Session`. Routers and UI routes call services instead of querying directly for domain operations.
- **API routers** (`app/api/`): one module per resource (projects, requirements, proposals, proposal_requirements, test_evidence, security_reviews, release_decisions, audit, traceability, release_readiness, auth). They are thin and handle HTTP concerns and RBAC dependencies.
- **UI routes** (`app/ui/routes.py`): server-rendered pages and form posts, with per-route auth and CSRF handling.

### Validation

lives in Pydantic schemas (`app/schemas/`), which define `*Create`, `*Update` and `*Response` models per resource. FastAPI validates request bodies against them, for example `ProposalCreate` and `TransitionRequest` in `app/schemas/proposal.py`. Workflow rules and release gates are enforced in `WorkflowService`, not in the schemas.

### Audit events

are appended in the service layer. Services such as `ProjectService`, `ProposalService`, `TestEvidenceService`, `SecurityReviewService`, `ReleaseDecisionService` and `WorkflowService` call `AuditService.create_audit_event` (`app/services/audit_service.py`) after a mutation. The UI adds events for its own actions through `_record_ui_audit`, which also goes through `AuditService`. `AuditService` offers create and read operations only. Requirement and proposal updates also write `EntityVersion` rows through `VersionHistoryService` (`app/services/version_history_service.py`).

## Data model

All tables are created by `Base.metadata.create_all` in `init_db()`. Each entry is the model class and its table.

- `Project` (`projects`, `app/models/project.py`): top-level container with a name and description.
- `Requirement` (`requirements`): belongs to a `Project` via `project_id`. It has a `requirement_id` label, a priority and a status (`active`, `deprecated`, `satisfied`).
- `Proposal` (`proposals`): belongs to a `Project`. It has a `proposal_id` label, `risk_level`, a JSON `files_expected` list and `workflow_status`.
- `ProposalRequirement` (`proposal_requirements`): link table with foreign keys to `proposals.id` and `requirements.id`.
- `TestEvidence` (`test_evidence`): many per `Proposal`. It records the test type, the command or procedure, and the result (`passed`, `failed`, `skipped`, `inconclusive`).
- `SecurityReview` (`security_reviews`): at most one per `Proposal` (unique `proposal_id`). Status is `pending`, `in_progress`, `passed`, `failed` or `waived`, plus a `risk_acceptance_reason`.
- `ReleaseDecision` (`release_decisions`): at most one per `Proposal` (unique `proposal_id`). The decision is `approved`, `rejected`, `deferred` or `conditional`.
- `WorkflowApprovalRequest` (`workflow_approval_requests`): an asynchronous request to move a proposal to `requested_status`. It carries `request_status` (`pending`, `approved`, `rejected`), the requester, the approver and decision reasons.
- `EntityVersion` (`entity_versions`): per-entity version history with `entity_type`, `entity_id`, `version_number` and before/after summaries.
- `AuditEvent` (`audit_events`): the audit log, with timestamp, actor, action (`create`, `update`, `delete`), entity type and id, and before/after summaries.
- `User` (`users`): local account with a unique username, `password_hash`, a `role`, `is_active`, `failed_login_attempts` and `locked_until`.
- `UserSession` (`user_sessions`): session record for a `User`, holding a unique `token_hash`, `expires_at`, `revoked_at` and `is_active`.

Relationships: `Project` 1-N `Requirement` and `Proposal`; `Proposal` N-M `Requirement` through `ProposalRequirement`; `Proposal` 1-N `TestEvidence` and `WorkflowApprovalRequest`; `Proposal` 1-1 `SecurityReview` and `ReleaseDecision`; `User` 1-N `UserSession`. `AuditEvent` and `EntityVersion` reference entities by type and id, not by foreign key.

## Workflow state machine

`Proposal.workflow_status` uses the `WorkflowStatus` enum (`app/models/proposal.py`). The allowed transitions are `VALID_TRANSITIONS` in `app/services/workflow_service.py`:

```
draft -> context_review -> implementation -> test_review
      -> security_review -> release_ready -> released
```

Each state has exactly one forward target, and `released` is terminal. There are no backward or skipping transitions.

`WorkflowService.transition_proposal` rejects any target that is not in `VALID_TRANSITIONS[current]`. For `security_review -> release_ready` it first runs `check_release_gates`, which requires:

1. At least one `ProposalRequirement` link.
2. At least one `TestEvidence` row.
3. A `SecurityReview` with status `passed`, or `waived` with a non-empty `risk_acceptance_reason`.
4. A `ReleaseDecision` row.

If any gate fails, the transition returns no proposal and a message listing each failed gate. On success the status is committed, an `AuditEvent` is appended, and `NotificationService.record_workflow_transition` writes to the local outbox.

The API exposes transitions at `POST /api/proposals/{proposal_id}/transition` (`app/api/proposals.py`). `WorkflowApprovalService` (`app/services/workflow_approval_service.py`) adds an optional approval step. `request_transition` creates a `pending` request without changing state. `approve_request` applies the transition through `WorkflowService.transition_proposal`, so the same validation and gates apply. `reject_request` records the rejection only. A request that is no longer pending cannot be decided again.

## Security architecture

### Global token guard

`app/main.py` attaches `_releaseguard_write_guard` as a router-level dependency to every `/api` router except `auth_router`. It calls `require_releaseguard_api_access` (`app/auth.py`) for paths where `is_protected_path` is true: any `/api` path other than `/api/auth`, for GET, POST, PUT, PATCH and DELETE. The guard accepts:

- A request whose `X-ReleaseGuard-Token` header matches the `RELEASEGUARD_WRITE_TOKEN` environment variable.
- A valid bearer session, when user auth is required.

With neither configured, requests pass, which is the local-development behavior.

### Per-router RBAC

`app/rbac.py` holds the role vocabulary (`owner`, `admin`, `finance`, `support`, `viewer`) and a static `POLICY` map from action names, such as `projects:write`, `audit:read`, `release:decide` and `admin:manage_users`, to allowed roles. Each router defines `_enforce_<resource>_read_rbac` and `_enforce_<resource>_write_rbac` dependencies, for example in `app/api/projects.py`. When user auth is required, each dependency allows a matching shared token. Otherwise it resolves the bearer session user, returns 401 if there is none, and returns 403 if `rbac.user_is_allowed` fails. Unknown actions and empty roles are never allowed. `require_role` in `app/rbac.py` is a dependency factory that expects a caller-supplied current-user resolver.

### Sessions

`SessionService` (`app/services/session_service.py`) issues tokens with `secrets.token_urlsafe(32)` and stores only the SHA-256 hex digest in `user_sessions.token_hash`. The raw token is returned once at creation. The default TTL is 8 hours. Lookup requires an active, unrevoked, unexpired row, and the owning user must be active. Bearer tokens come from the `Authorization` header. The UI uses the `releaseguard_ui_session` cookie, set `httponly` and `secure` in production mode.

### Passwords

`UserService` (`app/services/user_service.py`) hashes with PBKDF2-HMAC-SHA256 (`hashlib.pbkdf2_hmac`, 120,000 iterations), storing the algorithm, iterations, salt and digest in one string. Verification uses `hmac.compare_digest`.

### Lockout and rate limiting

After 5 consecutive failed logins `UserService` sets `locked_until` 15 minutes ahead. A successful login or an admin unlock or password reset clears the state. The UI login route also keeps an in-memory limiter keyed by client host and username: 5 failures in a 300-second window (`app/ui/routes.py`).

### CSRF on UI forms

`app/ui/routes.py` issues a signed token of the form `nonce:HMAC-SHA256(secret, binding:nonce)`. The binding is the UI session cookie, or `anonymous` when there is none. The signing secret comes from `RELEASEGUARD_CSRF_SECRET`, then the write token, then a fixed local-development value. The token is rendered into forms and also set as an `httponly`, `SameSite=Lax` cookie. `_enforce_csrf` requires the form value to equal the cookie and to carry a valid signature, otherwise it returns 403.

### UI auth

`_enforce_ui_auth` is applied per UI route. When user auth is required, it accepts a matching shared-token header, a bearer session or the UI session cookie, and otherwise returns 401.

### Fail-closed production mode

`RELEASEGUARD_ENV=prod` or `production` (`_production_mode` in `app/auth.py`) makes `_user_auth_required()` true regardless of `RELEASEGUARD_REQUIRE_USER_AUTH`. In that mode API and UI requests need a valid shared token or user session, and cookies are marked `secure`. User auth can also be turned on by itself with `RELEASEGUARD_REQUIRE_USER_AUTH` set to `1`, `true`, `yes` or `on`.

## Persistence

- **Engine** (`app/database.py`): `create_engine(settings.database_url)`, with `check_same_thread=False` for SQLite. `SessionLocal` is a `sessionmaker` with `autocommit=False` and `autoflush=False`. `get_db` yields one session per request and closes it afterwards.
- **WAL and busy timeout**: for file-backed SQLite URLs only (`_is_file_backed_sqlite` excludes `:memory:`), a `connect` event listener runs `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` on each new connection.
- **Schema creation and upgrades**: `init_db()` runs `Base.metadata.create_all` and then `ensure_sqlite_schema_upgrades`. That function is idempotent and SQLite-only. If the `users` table exists but lacks `failed_login_attempts` or `locked_until`, it adds them with `ALTER TABLE`. There is no general migration framework.
- **Backups** (`app/backup.py`): a stdlib-only module and CLI that does not import `app.database`.
  - `python -m app.backup create --database <file> --backup-dir <dir>` copies the database to `releaseguard-backup-<YYYYmmdd-HHMMSS>.db`.
  - `python -m app.backup restore --backup <file> --database <file>` removes the target's `-wal` and `-shm` sidecars and the old file, then copies the backup into place.
  - Both exit with status 2 on missing files or invalid arguments.
  - Backup uses a plain file copy, so take it while the application is idle or stopped.
