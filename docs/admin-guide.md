# ReleaseGuard Administrator Guide

This guide covers installing, configuring, securing and operating a ReleaseGuard instance. It describes the behavior of the current code only. For day-to-day usage see `docs/user-guide.md`.

## Installation

Requirements: Python 3.12 and a writable working directory for the SQLite file.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Tables are created automatically on application start (and by `scripts/create_owner.py` / `seed_data.py`).
- `GET /health` returns `{"status": "healthy", "version": ...}` and is never authenticated.
- Bind to `127.0.0.1` unless you front the service with a reverse proxy that terminates TLS. ReleaseGuard does not terminate TLS itself.
- Running `python -m app.main` binds `0.0.0.0:8000`; prefer the explicit `uvicorn` command above.

## Configuration

`.env.example` documents the variables. Only `DATABASE_URL` is loaded from a `.env` file by the settings layer. The `RELEASEGUARD_*` variables are read directly from the process environment, so export them in the service unit, shell or container definition rather than relying on `.env`.

| Variable | Default | Effect |
|----------|---------|--------|
| `DATABASE_URL` | `sqlite:///./releaseguard.db` | SQLAlchemy database URL. The default is a file in the process working directory. For file-backed SQLite, WAL mode and a 5000 ms busy timeout are enabled on every connection. |
| `RELEASEGUARD_WRITE_TOKEN` | unset | Shared API token. When set to a non-blank value, `/api` requests (except `/api/auth`) must carry a matching `X-ReleaseGuard-Token` header or receive `401`. Blank or whitespace is treated as unset. |
| `RELEASEGUARD_REQUIRE_USER_AUTH` | unset (off) | When `1`, `true`, `yes` or `on` (case-insensitive), `/api` and the browser UI require a valid user session and role policy is enforced. |
| `RELEASEGUARD_ENV` | unset | When `prod` or `production`, user authentication is forced on (fail-closed) and the UI session cookie is marked `Secure`. Any other value, including `development`, has no effect. |
| `RELEASEGUARD_OWNER_PASSWORD` | unset | Password for the first owner. Read only by `scripts/create_owner.py`; the script exits with an error if it is empty. It is not used by the running server. |
| `RELEASEGUARD_CSRF_SECRET` | unset | Signing secret for UI CSRF tokens. If unset, falls back to `RELEASEGUARD_WRITE_TOKEN`, then to a built-in development constant. Set a long random value whenever user auth is enabled. |

## Authentication modes

The mode is derived from the variables above and evaluated per request.

**1. Open local mode** (no auth variables set). All `/api` routes and all UI pages are accessible without credentials. Intended for a single-user workstation only.

**2. Shared token.** With `RELEASEGUARD_WRITE_TOKEN` set and user auth off, every `/api` request (all methods, including `GET`) must send:

```
X-ReleaseGuard-Token: <token>
```

A missing or wrong token returns `401`. The server-rendered UI pages are not gated by the token in this mode. The token identifies a caller as trusted but carries no role or identity.

**3. Full user auth with sessions.** With `RELEASEGUARD_REQUIRE_USER_AUTH=true`: <!-- driftwatch: ignore=env -->

- `POST /api/auth/login` with a JSON username and password returns a bearer token and its expiry. Sessions last 8 hours. Only a SHA-256 hash of the token is stored.
- Send `Authorization: Bearer <token>` on `/api` calls. `GET /api/auth/me` returns the current user; `POST /api/auth/logout` revokes the session.
- `/api/auth/*` is never behind the shared guard (login must be reachable).
- Browser users sign in at `/login`. The session is held in an `HttpOnly`, `SameSite=Lax` cookie (`releaseguard_ui_session`); state-changing UI forms carry a CSRF token.
- Each route then checks the user's role against the policy table (next section). Insufficient role returns `403`; no session returns `401`.
- If `RELEASEGUARD_WRITE_TOKEN` is also set, a request with the correct token header is accepted as an override and skips the role check. Treat the token as an administrator-level secret.

**4. Production fail-closed.** With `RELEASEGUARD_ENV=prod` (or `production`), mode 3 is active regardless of `RELEASEGUARD_REQUIRE_USER_AUTH`. A request without a valid session (or valid token override) is rejected, so a forgotten variable cannot leave the instance open. The session cookie is also issued with `Secure`, so the UI must be served over HTTPS. <!-- driftwatch: ignore=env -->

## Users and roles

### Roles

The five roles are `owner`, `admin`, `finance`, `support` and `viewer`. New users default to `viewer`. Role names are case-insensitive on input and stored lowercase.

### Permission matrix

Transcribed from the policy table in `app/rbac.py` (Y = allowed).

| Action | owner | admin | finance | support | viewer |
|--------|:-----:|:-----:|:-------:|:-------:|:------:|
| `projects:read` | Y | Y | Y | Y | Y |
| `projects:write` | Y | Y | | Y | |
| `requirements:read` | Y | Y | Y | Y | Y |
| `requirements:write` | Y | Y | | Y | |
| `proposals:read` | Y | Y | Y | Y | Y |
| `proposals:write` | Y | Y | Y | | |
| `proposal_requirements:read` | Y | Y | Y | Y | Y |
| `proposal_requirements:write` | Y | Y | Y | | |
| `test_evidence:read` | Y | Y | Y | Y | Y |
| `test_evidence:write` | Y | Y | | Y | |
| `security_reviews:read` | Y | Y | Y | Y | Y |
| `security_reviews:write` | Y | Y | | | |
| `release_decisions:read` | Y | Y | Y | Y | Y |
| `release:decide` | Y | Y | | | |
| `release-readiness:read` | Y | Y | Y | Y | Y |
| `traceability:read` | Y | Y | Y | Y | |
| `audit:read` | Y | Y | Y | | |
| `admin:manage_users` | Y | Y | | | |

An unknown action or an empty role is always denied.

### First-owner bootstrap

Run once on a fresh database, from the repository root with the venv active:

```bash
RELEASEGUARD_OWNER_PASSWORD='choose-a-strong-password' python scripts/create_owner.py --username owner
```

- `--username` defaults to `owner`. The password comes only from the environment variable, so it never appears in argv.
- The script initializes the database, then creates the user with display name "Owner".
- It refuses (exit 1) if any owner already exists, and exits 2 if the variable is unset or empty.
- Unset the variable from your shell afterwards.

### Managing users in the admin UI

Users with `admin:manage_users` (owner, admin) open `/admin/users` to:

- **Create a user:** username, password, optional display name, role. Duplicate usernames and invalid roles are rejected with `400`.
- **Unlock** an account: clears the failed-attempt counter and lockout timestamp.
- **Reset a password:** sets a new password and also clears any lockout.

User creation is recorded in the audit log. Passwords are stored as PBKDF2-HMAC-SHA256 hashes (120,000 iterations, 16-byte random salt).

### Lockout and login rate limiting

- **Account lockout:** after 5 consecutive failed passwords an account is locked for 15 minutes. A locked account cannot log in even with the right password until the window ends or an administrator unlocks it. A successful login resets the counter.
- **UI rate limit:** the `/login` form allows 5 failures per 5-minute window per (client IP, lowercased username) pair, then answers `429` ("Too many login attempts"). A successful login clears that pair's failures. The counters are held in process memory and reset on restart. Behind a reverse proxy the client IP seen is the proxy's unless the server is configured to trust forwarded headers.
- Failed and successful UI logins are written to the audit log.

## Database operations

- **Engine and location:** SQLite by default, file `releaseguard.db` in the working directory the server was started from (override with `DATABASE_URL`). Use an absolute path, e.g. `sqlite:////var/lib/releaseguard/releaseguard.db`, so the location does not depend on the launch directory.
- **WAL mode:** recent writes may sit in `releaseguard.db-wal` with a shared-memory file `releaseguard.db-shm` beside the database. These are normal. Never delete them while the server runs.
- **What to back up:** the database file is the only state (users, session hashes, projects, evidence, decisions and the audit log). Keep the environment definition (service unit, container spec or `.env`) as well, since it holds the configuration and secrets.

### Backup

```bash
python -m app.backup create --database /var/lib/releaseguard/releaseguard.db --backup-dir /var/backups/releaseguard
```

This prints the path of a new file named `releaseguard-backup-YYYYMMDD-HHMMSS.db`. It exits 2 if the source is missing.

The helper performs a plain file copy of the main database file only; it does not include the `-wal` sidecar. To get a consistent snapshot, stop the server (or make sure no writes are in flight) before backing up.

### Restore

1. Stop the server.
2. Run:

   ```bash
   python -m app.backup restore --backup /var/backups/releaseguard/releaseguard-backup-20260101-120000.db --database /var/lib/releaseguard/releaseguard.db
   ```

3. Start the server.

Restore deletes the existing target database and any `-wal` / `-shm` sidecars, then copies the backup into place. It exits 2 if the backup file is not found. Test restores on a scratch path first. Sessions in the restored file keep their original expiry.

## Seeding demo data

`seed_data.py` creates a demo project with requirements, proposals and related records for evaluation:

```bash
python seed_data.py
```

If the database already contains any project, the script prints an error and exits 1 without changing anything. `--force` overrides this guard and adds the demo records alongside existing data:

```bash
python seed_data.py --force
```

Do not seed a production database. Use a separate `DATABASE_URL` for demos.

## Security model and accepted risks

**What is protected**

- API access control by shared token and/or bearer sessions, with a fail-closed production switch.
- Role-based authorization for API routes and for the UI routes `/traceability`, `/audit` and `/admin/users*`.
- Passwords hashed with salted PBKDF2; session tokens are random, expire after 8 hours, are revocable, and are stored only as hashes.
- Account lockout and per-IP-and-user login rate limiting.
- CSRF tokens on UI forms, bound to the session cookie; `HttpOnly` and `SameSite=Lax` session cookie, `Secure` in production.
- Response headers `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`.
- Audit events recorded for changes, user creation and UI logins.

**Encryption at rest** is not performed by ReleaseGuard. The SQLite file and its backups are stored unencrypted. Rely on host disk encryption (FileVault on macOS, LUKS or equivalent on Linux, BitLocker on Windows) and restrict filesystem permissions on the database and backup directory. Terminate TLS at a reverse proxy for data in transit.

**Accepted risks and residual notes**

- **Actor header not bound to session.** Mutating API calls accept an `actor` header that is written to the audit log as supplied. It is not verified against the authenticated user, so audit `actor` values on API changes are advisory. UI-originated audit events use the logged-in username.
- **UI detail pages require login but not per-role read policy.** With user auth on, any authenticated user (including `viewer`) can open the UI list and detail pages. Only `/traceability`, `/audit` and `/admin/users*` apply role checks in the UI. The API read policy in the matrix is enforced on `/api` routes.
- **Shared token overrides user auth.** Anyone holding `RELEASEGUARD_WRITE_TOKEN` bypasses role checks and has no individual identity. Rotate it if exposed.
- **In-memory rate limiter.** Limits reset on restart and are not shared across multiple server processes. Lockout, which is stored in the database, still applies.
- **Open local mode is unauthenticated** by design. Never expose it beyond localhost.
- **Development CSRF fallback.** Without `RELEASEGUARD_CSRF_SECRET` or a write token, CSRF tokens are signed with a public constant. Always set the secret outside local use.
