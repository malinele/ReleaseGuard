# Changelog

All notable changes to ReleaseGuard are documented in this file.

## [Unreleased]

### Added
- `.env.example` documenting supported environment variables, including
  `DATABASE_URL` and `RELEASEGUARD_OWNER_PASSWORD`.

## [1.0.0]

### Added
- Local multi-user authentication (KI-001): users, sessions, RBAC policy
  enforced on all `/api` routes and role-restricted UI routes, login/logout UI
  with CSRF protection, rate limiting, account lockout, and audit events.
- First-owner bootstrap CLI (`scripts/create_owner.py`), reading the password
  from `RELEASEGUARD_OWNER_PASSWORD`.
- Route-inventory guard test ensuring `/api` routes are RBAC-gated.

### Changed
- Documentation (`deployment.md`, README, known issues) aligned with the
  implemented behavior; KI-001 closed with residual notes.
