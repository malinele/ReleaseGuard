# ReleaseGuard User Guide

This guide shows you how to run ReleaseGuard and use it to track a change from first draft to release. It describes what the application does today.

## What ReleaseGuard does

ReleaseGuard is release governance for software delivery. It keeps the evidence for each release in one place, and it refuses to move a change toward release until that evidence exists.

You work with these concepts:

- **Project** (`name`, `description`): the product or system you ship.
- **Requirement** (`requirement_id` such as `REQ-001`, `title`, `description`, `acceptance_criteria`, `priority`, `status`): something the software must do. Priority is `low`, `medium`, `high` or `critical`. Status is `active`, `deprecated` or `satisfied`.
- **Change proposal** (`proposal_id` such as `PROP-001`, `summary`, `generated_by`, `files_expected`, `risk_level`, `rationale`, `workflow_status`): one proposed change. It is the unit that moves through the workflow. Risk level is `low`, `medium` (the default), `high` or `critical`.
- **Test evidence** (`test_type`, `command_or_procedure`, `result`, `evidence_notes`): a record that the change was tested, and how.
- **Security review** (`status`, `reviewer`, `notes`, `risk_acceptance_reason`): one review per proposal.
- **Release decision** (`decision`, `decision_maker`, `decision_notes`): one decision per proposal.
- **Audit log**: an append-only record of who changed what and when.

The workflow has seven statuses: `draft`, `context_review`, `implementation`, `test_review`, `security_review`, `release_ready`, `released`.

Why each gate exists:

| Gate | Why it exists |
| --- | --- |
| Linked requirements | A change that satisfies no requirement has no stated purpose, so you cannot check it against anything. |
| Test evidence | A claim that something works is not enough. You must record the command or procedure and the result. |
| Security review passed, or waived with a reason | Someone accountable must either clear the change or knowingly accept the risk and write down why. |
| Release decision | A named person makes the final call, and that call is recorded. |
| Audit log | After the fact, you can show who did what and what changed. |

## First steps

1. Install, from the repository root:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

2. Optionally set a write token. When it is set, every request to `/api` (except `/api/auth`) must send it in the `X-ReleaseGuard-Token` header:

   ```bash
   export RELEASEGUARD_WRITE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
   ```

3. Load the demo data (optional, recommended for a first look):

   ```bash
   python seed_data.py
   ```

   This creates the project "ReleaseGuard Core" with requirements `REQ-001` to `REQ-003`, proposal `PROP-001`, unit and integration test evidence, a passed security review, an approved release decision, and then moves the proposal through the workflow. If the database already contains projects, the script refuses to run. Use `python seed_data.py --force` to seed anyway. The database is `sqlite:///./releaseguard.db` unless you set `DATABASE_URL`.

4. Create the first owner account. The password comes from the environment only, and the script refuses to run if an owner already exists:

   ```bash
   RELEASEGUARD_OWNER_PASSWORD='choose-a-strong-password' python scripts/create_owner.py --username owner
   ```

5. Start the server:

   ```bash
   uvicorn app.main:app --reload
   ```

6. Open `http://127.0.0.1:8000/login` and sign in. Without user authentication enabled, the pages work without signing in. To require sign-in, set `RELEASEGUARD_REQUIRE_USER_AUTH=true`, or `RELEASEGUARD_ENV=production`. Production mode also requires a valid session or the write token on every protected route. In production, set `RELEASEGUARD_CSRF_SECRET` as well. <!-- driftwatch: ignore=env -->

Other useful addresses: `/docs` (interactive API documentation), `/health` (status and version).

### Roles

Each user has one role: `owner`, `admin`, `finance`, `support` or `viewer` (the default). When user authentication is on, the role decides what you may do:

| Action | Roles |
| --- | --- |
| Read projects, requirements, proposals, test evidence, security reviews, release decisions, release readiness | owner, admin, finance, support, viewer |
| Write projects and requirements | owner, admin, support |
| Write proposals, link requirements to proposals | owner, admin, finance |
| Write test evidence | owner, admin, support |
| Write security reviews | owner, admin |
| Record a release decision | owner, admin |
| Read traceability | owner, admin, finance, support |
| Read audit log | owner, admin, finance |
| Manage users (`/admin/users`) | owner, admin |

A request that carries the correct `X-ReleaseGuard-Token` bypasses these role checks.

To get an API session, `POST /api/auth/login` with `username` and `password`. It returns an `access_token` and `expires_at`. Send the token as `Authorization: Bearer <token>`. `GET /api/auth/me` shows who you are, and `POST /api/auth/logout` ends the session.

Owners and admins can create users at `/admin/users` (username, password, display name, role), unlock locked accounts, and reset passwords. Repeated failed logins lock an account for a period, and the login form rate-limits attempts.

## Working with projects and requirements

Create and list through the API. Examples use the write token; leave out the header if you did not set one.

```bash
curl -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" -H "X-ReleaseGuard-Token: $RELEASEGUARD_WRITE_TOKEN" \
  -d '{"name": "Payments", "description": "Payment service"}'

curl -X POST http://127.0.0.1:8000/api/requirements \
  -H "Content-Type: application/json" -H "X-ReleaseGuard-Token: $RELEASEGUARD_WRITE_TOKEN" \
  -d '{"project_id": 1, "requirement_id": "REQ-010", "title": "Refunds", "priority": "high", "acceptance_criteria": "A refund is issued within 24h"}'
```

Endpoints:

- `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/{project_id}`
- `GET/POST /api/requirements`, `GET/PUT/DELETE /api/requirements/{requirement_id}`

Both list endpoints accept `skip` (default 0) and `limit` (default 100). `/api/requirements` also accepts `project_id`.

**Searching.** Add `q` to either list. The match is a case-insensitive substring. Projects search `name` and `description`. Requirements search `requirement_id`, `title` and `description`.

```bash
curl "http://127.0.0.1:8000/api/requirements?project_id=1&q=refund"
```

Note that the `id` in a URL is the database id, not the `REQ-010` style `requirement_id`.

**What the pages show:**

- `/` is the dashboard: all projects, the 10 most recent proposals (ID, summary, risk level, status), and the 5 most recent audit events.
- `/projects` lists projects. `/projects/{project_id}` shows one project with its requirements and proposals.
- `/requirements` lists requirements across projects. `/requirements/{requirement_id}` shows one requirement and the proposals linked to it.

The UI pages are read-only views. You create and change data through the API.

## Change proposals and the workflow

Create a proposal with `POST /api/proposals`:

```json
{"project_id": 1, "proposal_id": "PROP-010", "summary": "Add refund endpoint",
 "generated_by": "assistant-name", "files_expected": ["app/refunds.py"],
 "risk_level": "high", "rationale": "Customer request"}
```

List with `GET /api/proposals` (optional `project_id`, `skip`, `limit`). Link requirements with `POST /api/proposals/{proposal_id}/requirements` and body `{"proposal_id": 1, "requirement_id": 1}` (database ids; `proposal_id` must match the URL). `GET` on the same path lists the links. `DELETE /api/proposals/{proposal_id}/requirements/{req_id}` removes one.

A new proposal starts in `draft`. It moves forward one step at a time:

```
draft -> context_review -> implementation -> test_review -> security_review -> release_ready -> released
```

There are no skips and no backward moves. `released` is final. Any other target gives `400 Invalid transition from X to Y`.

Move a proposal with:

```bash
curl -X POST http://127.0.0.1:8000/api/proposals/1/transition \
  -H "Content-Type: application/json" -H "X-ReleaseGuard-Token: $RELEASEGUARD_WRITE_TOKEN" \
  -d '{"target_status": "context_review", "actor": "jane"}'
```

**What blocks a transition.** All steps are free except `security_review -> release_ready`. For that step ReleaseGuard checks four gates and refuses if any fails. The `400` response lists every failed gate:

1. At least one requirement is linked ("Gate 1 failed: No requirements linked to proposal").
2. At least one test evidence record exists.
3. A security review exists and its status is `passed`, or `waived` with a `risk_acceptance_reason`.
4. A release decision exists.

Check this ahead of time with `GET /api/release-readiness`. It returns `total_proposals`, `release_ready`, `blocked`, and for each proposal its `workflow_status`, `gates_passed` and `missing_gates`.

**Approval requests.** The application also has a "workflow approval request" record (requested status, requester, approver, reason, decision reason, and a `pending`/`approved`/`rejected` status). Approving a request applies the transition with the same rules and gates. Rejecting it changes nothing. There are no API routes or pages for approval requests in this version, so they are not reachable from the browser or HTTP.

Every transition writes an audit event.

## Test evidence and security review

**Test evidence.** Record one entry per test run or manual check:

```bash
curl -X POST http://127.0.0.1:8000/api/proposals/1/test-evidence \
  -H "Content-Type: application/json" -H "X-ReleaseGuard-Token: $RELEASEGUARD_WRITE_TOKEN" \
  -d '{"proposal_id": 1, "test_type": "unit", "command_or_procedure": "python -m pytest -q", "result": "passed", "evidence_notes": "42 passed"}'
```

- `test_type`: `unit`, `integration`, `system`, `manual` or `automated`.
- `result`: `passed`, `failed`, `skipped` or `inconclusive`.
- `command_or_procedure` is required. Write the exact command or the manual steps so someone else can repeat them.

Other routes: `GET /api/proposals/{proposal_id}/test-evidence`, `PUT /api/test-evidence/{evidence_id}`, `DELETE /api/test-evidence/{evidence_id}`.

The release gate only requires that at least one record exists. It does not look at `result`. A record with `failed` still satisfies Gate 2, so read the evidence before you decide.

**Security review.** There is one review per proposal, at `/api/proposals/{proposal_id}/security-review` (`GET`, `POST`). The body fields are `proposal_id`, `status`, `reviewer`, `notes` and `risk_acceptance_reason`. Status is `pending` (default), `in_progress`, `passed`, `failed` or `waived`.

To waive a review, set `status` to `waived` and fill in `risk_acceptance_reason`. A waived review with no reason fails Gate 3. `pending`, `in_progress` and `failed` also fail it.

## Release decisions

Record the decision at `/api/proposals/{proposal_id}/release-decision`:

```bash
curl -X POST http://127.0.0.1:8000/api/proposals/1/release-decision \
  -H "Content-Type: application/json" -H "X-ReleaseGuard-Token: $RELEASEGUARD_WRITE_TOKEN" \
  -d '{"proposal_id": 1, "decision": "approved", "decision_maker": "release_manager", "decision_notes": "All gates passed"}'
```

`decision` is `approved`, `rejected`, `deferred` or `conditional`. `GET` on the same path returns the decision, or `404` if none exists. There is one decision per proposal.

**Who may decide.** With user authentication on, only the `owner` and `admin` roles can record a release decision. Other roles get `403`.

**What is checked.** Recording a decision does not itself run the gates. The `proposal_id` in the body must match the URL (otherwise `400`). The four-gate check runs when the proposal moves from `security_review` to `release_ready`, and the existence of a decision is one of those gates. So the usual order is: link requirements, add test evidence, complete the security review, record the decision, then move the proposal to `release_ready`, and finally to `released`. The `decision` value (for example `rejected`) is stored but is not read by the gate; the gate only checks that a decision exists. Make sure the moves to `release_ready` and `released` match the decision.

## Traceability and audit

**Traceability.**

- `/traceability` shows a matrix: each requirement, the proposals linked to it, and their test evidence. It needs the `traceability:read` role (owner, admin, finance, support) when user authentication is on.
- `/evidence` is the evidence dashboard. It lists test evidence, security reviews, release decisions and proposals.
- `/proposals/{proposal_id}` shows one proposal with its fields, linked requirements, test evidence, security review and release decision.
- `GET /api/traceability` returns everything: projects, requirements, proposals, test evidence, security reviews and release decisions.
- `GET /api/traceability/proposal/{proposal_id}` returns the chain for one proposal: its project, linked requirements, test evidence, security review and release decision.

To answer "what proved this requirement was met", start at the requirement page, open a linked proposal, and read its evidence, review and decision.

**Audit log.**

- `/audit` lists every event, newest first: timestamp, actor, action, entity, and before/after summaries. It needs the `audit:read` role (owner, admin, finance).
- Each event has an `action` of `create`, `update` or `delete`, an `entity_type`, an `entity_id`, an `actor`, and `before_summary` / `after_summary`.
- `GET /api/audit` accepts `entity_type`, `entity_id` and `limit` (default 100, maximum 500).
- `GET /api/audit/{audit_id}` returns one event.
- `GET /api/audit/export` accepts `entity_type`, `entity_id`, `actor` and `limit` (1 to 500). It returns `total_events`, the `filters` you applied, a `summary` (counts `by_action`, `by_entity_type`, and per `actors`), and the `events`.

```bash
curl "http://127.0.0.1:8000/api/audit/export?entity_type=proposal&entity_id=1" > proposal-1-audit.json
```

The actor is taken from the `actor` header on create and update calls (and from the `actor` field on a transition). If you leave it out, the event has no actor, so send it every time. The application has no route that edits or deletes audit events. The `actor` filter on export applies after the `limit`, so raise `limit` if you filter by actor on a busy log.

## Version history and backups

**Entity versions.** Each time you update a requirement or a proposal through `PUT`, ReleaseGuard stores a version row: `entity_type`, `entity_id`, a `version_number` that counts up from 1 for that entity, the `actor`, and `before_summary` and `after_summary`. The audit log gets a matching event. Version rows are stored in the database. There is no page or API route for listing them in this version.

One caution about proposals: `PUT /api/proposals/{proposal_id}` accepts `workflow_status` among its fields and writes it directly. That edit does not go through the transition rules or the release gates. Use `/transition` for status changes, and limit `proposals:write` to people who should not skip the workflow.

**Backups.** Backups are plain copies of the SQLite database file. Stop the server before you restore.

```bash
python -m app.backup create --database releaseguard.db --backup-dir backups
```

This copies the database into `backups/` as `releaseguard-backup-YYYYMMDD-HHMMSS.db` and prints the path. It creates the directory if needed. If the database file does not exist, it exits with status 2.

```bash
python -m app.backup restore --backup backups/releaseguard-backup-20250101-120000.db --database releaseguard.db
```

This replaces the target database with the backup, removes any leftover `-wal` and `-shm` files next to it, and prints the target path. It overwrites the current database without asking, so make a fresh backup first if you may need the current state. The tool only works with file-based SQLite databases, not with other `DATABASE_URL` values.
