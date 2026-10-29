"""ReleaseGuard UI Routes - Readonly browser views."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth import (
    WRITE_TOKEN_HEADER,
    _configured_token,
    _production_mode,
    _user_auth_required,
    get_releaseguard_user_session,
)
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.proposal import Proposal
from app.models.proposal_requirement import ProposalRequirement
from app.models.test_evidence import TestEvidence
from app.models.security_review import SecurityReview
from app.models.release_decision import ReleaseDecision
from app.models.audit_event import AuditAction, AuditEvent
from app.rbac import is_role_allowed
from app.services.audit_service import AuditService
from app.services.session_service import SessionService
from app.services.user_service import UserService

templates = Jinja2Templates(directory="app/ui/templates")

router = APIRouter(prefix="", tags=["ui"])

UI_SESSION_COOKIE = "releaseguard_ui_session"
UI_CSRF_COOKIE = "releaseguard_ui_csrf"
UI_CSRF_SECRET_ENV = "RELEASEGUARD_CSRF_SECRET"
_ANONYMOUS_CSRF_BINDING = "anonymous"
_LOCAL_DEV_CSRF_SECRET = "releaseguard-local-dev-csrf-secret"
LOGIN_RATE_LIMIT_MAX_FAILURES = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300
_LOGIN_RATE_LIMIT: dict[tuple[str, str], list[float]] = {}


def _get_ui_cookie_user(request: Request, db: Session) -> Optional[User]:
    """Return the active user for the UI session cookie, if present."""
    token = request.cookies.get(UI_SESSION_COOKIE)
    if not token:
        return None
    session = SessionService.get_session_for_token(db, token)
    if not session:
        return None
    return (
        db.query(User)
        .filter(
            User.id == session.user_id,
            User.is_active.is_(True),
        )
        .first()
    )


def _csrf_secret() -> str:
    """Return the configured CSRF signing secret, with local-dev fallback."""
    return (
        os.environ.get(UI_CSRF_SECRET_ENV, "").strip()
        or _configured_token()
        or _LOCAL_DEV_CSRF_SECRET
    )


def _csrf_binding(request: Request) -> str:
    """Bind CSRF tokens to the UI session cookie when one exists."""
    return request.cookies.get(UI_SESSION_COOKIE) or _ANONYMOUS_CSRF_BINDING


def _sign_csrf_token(nonce: str, binding: str) -> str:
    message = f"{binding}:{nonce}".encode("utf-8")
    return hmac.new(
        _csrf_secret().encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _create_csrf_token(binding: str) -> str:
    nonce = secrets.token_urlsafe(32)
    return f"{nonce}:{_sign_csrf_token(nonce, binding)}"


def _csrf_token_is_valid(token: Optional[str], request: Request) -> bool:
    if not token or ":" not in token:
        return False
    nonce, signature = token.split(":", 1)
    if not nonce or not signature:
        return False
    expected = _sign_csrf_token(nonce, _csrf_binding(request))
    return hmac.compare_digest(signature, expected)


def _csrf_token_for_response(request: Request) -> str:
    token = request.cookies.get(UI_CSRF_COOKIE)
    if not _csrf_token_is_valid(token, request):
        token = _create_csrf_token(_csrf_binding(request))
    return token


def _set_csrf_cookie(response, token: str) -> None:
    response.set_cookie(
        UI_CSRF_COOKIE,
        token,
        httponly=True,
        secure=_production_mode(),
        samesite="lax",
    )


def _render_template(
    request: Request,
    template_name: str,
    context: dict,
    *,
    status_code: int = status.HTTP_200_OK,
):
    csrf_token = _csrf_token_for_response(request)
    context_with_csrf = dict(context)
    context_with_csrf["csrf_token"] = csrf_token
    response = templates.TemplateResponse(
        request,
        template_name,
        context_with_csrf,
        status_code=status_code,
    )
    _set_csrf_cookie(response, csrf_token)
    return response


def _enforce_csrf(request: Request, csrf_token: str) -> None:
    cookie_token = request.cookies.get(UI_CSRF_COOKIE)
    if (
        not cookie_token
        or not hmac.compare_digest(cookie_token, csrf_token)
        or not _csrf_token_is_valid(csrf_token, request)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


def _record_ui_audit(
    db: Session,
    *,
    action: AuditAction,
    entity_type: str,
    entity_id: Optional[int],
    actor: Optional[str],
    after_summary: str,
) -> None:
    """Record a UI audit event without storing credentials or token material."""
    AuditService.create_audit_event(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        after_summary=after_summary,
    )


def _login_rate_limit_key(request: Request, username: str) -> tuple[str, str]:
    client_host = request.client.host if request.client else "unknown"
    return client_host, username.strip().lower()


def _login_rate_limit_failures(key: tuple[str, str], now: float) -> list[float]:
    cutoff = now - LOGIN_RATE_LIMIT_WINDOW_SECONDS
    failures = [
        timestamp
        for timestamp in _LOGIN_RATE_LIMIT.get(key, [])
        if timestamp >= cutoff
    ]
    _LOGIN_RATE_LIMIT[key] = failures
    return failures


def _login_rate_limit_exceeded(request: Request, username: str) -> bool:
    key = _login_rate_limit_key(request, username)
    failures = _login_rate_limit_failures(key, time.monotonic())
    return len(failures) >= LOGIN_RATE_LIMIT_MAX_FAILURES


def _record_login_failure(request: Request, username: str) -> None:
    key = _login_rate_limit_key(request, username)
    failures = _login_rate_limit_failures(key, time.monotonic())
    failures.append(time.monotonic())
    _LOGIN_RATE_LIMIT[key] = failures


def _clear_login_failures(request: Request, username: str) -> None:
    _LOGIN_RATE_LIMIT.pop(_login_rate_limit_key(request, username), None)


def _enforce_ui_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Require an authenticated user for UI routes only when user auth is enabled."""
    if not _user_auth_required():
        return None

    expected = _configured_token()
    provided = request.headers.get(WRITE_TOKEN_HEADER)
    if expected and provided == expected:
        return None

    user = get_releaseguard_user_session(request, db)
    if user is None:
        user = _get_ui_cookie_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for UI access",
        )
    return user


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    """Render the local UI login form."""
    return _render_template(
        request,
        "login.html",
        {"error": None},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    """Validate a local user and set a browser session cookie."""
    _enforce_csrf(request, csrf_token)
    if _login_rate_limit_exceeded(request, username):
        return _render_template(
            request,
            "login.html",
            {"error": "Too many login attempts. Try again later."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    user = UserService.get_user_by_username(db, username)
    if user and UserService.user_is_locked(user):
        return _render_template(
            request,
            "login.html",
            {"error": "Account locked. Try again later."},
            status_code=status.HTTP_423_LOCKED,
        )
    if not UserService.verify_user_password(db, username, password):
        _record_login_failure(request, username)
        if user:
            UserService.record_failed_login(db, user)
        _record_ui_audit(
            db,
            action=AuditAction.CREATE,
            entity_type="user_session",
            entity_id=None,
            actor=username.strip() or None,
            after_summary="ui_login_failed",
        )
        return _render_template(
            request,
            "login.html",
            {"error": "Invalid username or password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user is None:
        _record_login_failure(request, username)
        _record_ui_audit(
            db,
            action=AuditAction.CREATE,
            entity_type="user_session",
            entity_id=None,
            actor=username.strip() or None,
            after_summary="ui_login_failed",
        )
        return _render_template(
            request,
            "login.html",
            {"error": "Invalid username or password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    created = SessionService.create_session(db, user_id=user.id)
    _clear_login_failures(request, username)
    _record_ui_audit(
        db,
        action=AuditAction.CREATE,
        entity_type="user_session",
        entity_id=user.id,
        actor=user.username,
        after_summary="ui_login_success",
    )
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        UI_SESSION_COOKIE,
        created.token,
        httponly=True,
        secure=_production_mode(),
        samesite="lax",
    )
    _set_csrf_cookie(response, _create_csrf_token(created.token))
    return response


@router.post("/logout")
async def logout_submit(
    request: Request,
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
):
    """Revoke the UI session cookie when it maps to an active session."""
    _enforce_csrf(request, csrf_token)
    token = request.cookies.get(UI_SESSION_COOKIE)
    if token:
        session = SessionService.get_session_for_token(db, token)
        if session:
            user = db.query(User).filter(User.id == session.user_id).first()
            SessionService.revoke_session(db, session.id)
            _record_ui_audit(
                db,
                action=AuditAction.UPDATE,
                entity_type="user_session",
                entity_id=session.user_id,
                actor=user.username if user else None,
                after_summary="ui_logout",
            )

    target = "/login" if _user_auth_required() else "/"
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(UI_SESSION_COOKIE)
    response.delete_cookie(UI_CSRF_COOKIE)
    return response


def _enforce_ui_role(user: Optional[User], action: str) -> None:
    """Apply role policy when UI auth resolved a user session."""
    if user is None:
        return None
    if not is_role_allowed(user.role, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"forbidden: role '{user.role}' may not '{action}'",
        )
    return None


def _users_context(
    db: Session,
    *,
    error: Optional[str] = None,
    message: Optional[str] = None,
) -> dict:
    """Build template context for the local user-management page."""
    users = db.query(User).order_by(User.username.asc()).all()
    return {
        "users": users,
        "locked_user_ids": {
            user.id for user in users if UserService.user_is_locked(user)
        },
        "roles": ("owner", "admin", "finance", "support", "viewer"),
        "error": error,
        "message": message,
    }


@router.get("/", response_class=HTMLResponse)
async def root_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Root dashboard - overview of all projects and recent activity."""
    projects = db.query(Project).all()
    recent_proposals = db.query(Proposal).order_by(Proposal.created_at.desc()).limit(10).all()
    recent_audits = db.query(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(5).all()
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "projects": projects,
            "recent_proposals": recent_proposals,
            "recent_audits": recent_audits,
            "csrf_token": csrf_token,
        }
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/projects", response_class=HTMLResponse)
async def projects_list(
    request: Request,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """List all projects."""
    projects = db.query(Project).all()
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "project_list.html",
        {"projects": projects, "csrf_token": csrf_token}
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/evidence", response_class=HTMLResponse)
async def evidence_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Evidence dashboard - readonly view of test evidence, security reviews, release decisions, and proposals."""
    test_evidence = db.query(TestEvidence).all()
    security_reviews = db.query(SecurityReview).all()
    release_decisions = db.query(ReleaseDecision).all()
    proposals = db.query(Proposal).order_by(Proposal.created_at.desc()).all()
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "evidence.html",
        {
            "test_evidence": test_evidence,
            "security_reviews": security_reviews,
            "release_decisions": release_decisions,
            "proposals": proposals,
            "csrf_token": csrf_token,
        }
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Project detail view with requirements and proposals."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return HTMLResponse(content="Project not found", status_code=404)
    requirements = db.query(Requirement).filter(Requirement.project_id == project_id).all()
    proposals = db.query(Proposal).filter(Proposal.project_id == project_id).all()
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "project_detail.html",
        {
            "project": project,
            "requirements": requirements,
            "proposals": proposals,
            "csrf_token": csrf_token,
        }
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/requirements", response_class=HTMLResponse)
async def requirements_list(
    request: Request,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """List all requirements across projects."""
    requirements = db.query(Requirement).all()
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "requirement_list.html",
        {"requirements": requirements, "csrf_token": csrf_token}
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/requirements/{requirement_id}", response_class=HTMLResponse)
async def requirement_detail(
    request: Request,
    requirement_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Requirement detail view with linked proposals."""
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
    if not requirement:
        return HTMLResponse(content="Requirement not found", status_code=404)
    # Find proposals that reference this requirement
    linked = db.query(ProposalRequirement).filter(ProposalRequirement.requirement_id == requirement_id).all()
    proposal_ids = [link.proposal_id for link in linked]
    proposals = db.query(Proposal).filter(Proposal.id.in_(proposal_ids)).all() if proposal_ids else []
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "requirement_detail.html",
        {
            "requirement": requirement,
            "proposals": proposals,
            "csrf_token": csrf_token,
        }
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/proposals/{proposal_id}", response_class=HTMLResponse)
async def proposal_detail(
    request: Request,
    proposal_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Proposal detail view with requirements, test evidence, security review, release decision."""
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        return HTMLResponse(content="Proposal not found", status_code=404)
    # Get linked requirements
    links = db.query(ProposalRequirement).filter(ProposalRequirement.proposal_id == proposal_id).all()
    req_ids = [link.requirement_id for link in links]
    requirements = db.query(Requirement).filter(Requirement.id.in_(req_ids)).all() if req_ids else []
    # Get test evidence
    test_evidence = db.query(TestEvidence).filter(TestEvidence.proposal_id == proposal_id).all()
    # Get security review
    security_review = db.query(SecurityReview).filter(SecurityReview.proposal_id == proposal_id).first()
    # Get release decision
    release_decision = db.query(ReleaseDecision).filter(ReleaseDecision.proposal_id == proposal_id).first()
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "proposal_detail.html",
        {
            "proposal": proposal,
            "requirements": requirements,
            "test_evidence": test_evidence,
            "security_review": security_review,
            "release_decision": release_decision,
            "csrf_token": csrf_token,
        }
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/traceability", response_class=HTMLResponse)
async def traceability_view(
    request: Request,
    db: Session = Depends(get_db),
    authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Traceability matrix - requirements to proposals to test evidence."""
    _enforce_ui_role(authorized_user, "traceability:read")
    requirements = db.query(Requirement).all()
    proposals = db.query(Proposal).all()
    test_evidence = db.query(TestEvidence).all()
    # Build traceability links
    proposal_requirements = db.query(ProposalRequirement).all()
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "traceability.html",
        {
            "requirements": requirements,
            "proposals": proposals,
            "test_evidence": test_evidence,
            "proposal_requirements": proposal_requirements,
            "csrf_token": csrf_token,
        }
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/audit", response_class=HTMLResponse)
async def audit_view(
    request: Request,
    db: Session = Depends(get_db),
    authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Audit log view - all system actions with timestamps."""
    _enforce_ui_role(authorized_user, "audit:read")
    audit_logs = db.query(AuditEvent).order_by(AuditEvent.timestamp.desc()).all()
    csrf_token = _csrf_token_for_response(request)
    response = templates.TemplateResponse(
        request,
        "audit_log.html",
        {"audit_logs": audit_logs, "csrf_token": csrf_token}
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    db: Session = Depends(get_db),
    authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Local user-management page for owner/admin users."""
    _enforce_ui_role(authorized_user, "admin:manage_users")
    return _render_template(
        request,
        "admin_users.html",
        _users_context(db),
    )


@router.post("/admin/users")
async def admin_users_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
    role: str = Form("viewer"),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Create a local user from the owner/admin browser UI."""
    _enforce_ui_role(authorized_user, "admin:manage_users")
    _enforce_csrf(request, csrf_token)
    try:
        created_user = UserService.create_user(
            db,
            username=username,
            password=password,
            display_name=display_name.strip() or None,
            role=role,
        )
        _record_ui_audit(
            db,
            action=AuditAction.CREATE,
            entity_type="user",
            entity_id=created_user.id,
            actor=authorized_user.username if authorized_user else None,
            after_summary=(
                f"ui_user_created username={created_user.username} "
                f"role={created_user.role}"
            ),
        )
    except ValueError as exc:
        return _render_template(
            request,
            "admin_users.html",
            _users_context(db, error=str(exc)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    response = RedirectResponse("/admin/users", status_code=status.HTTP_303_SEE_OTHER)
    return response


@router.post("/admin/users/{user_id}/unlock")
async def admin_users_unlock(
    request: Request,
    user_id: int,
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Clear lockout state for a local user from the owner/admin browser UI."""
    _enforce_ui_role(authorized_user, "admin:manage_users")
    _enforce_csrf(request, csrf_token)
    try:
        unlocked_user = UserService.unlock_user(db, user_id)
    except ValueError as exc:
        return _render_template(
            request,
            "admin_users.html",
            _users_context(db, error=str(exc)),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    _record_ui_audit(
        db,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=unlocked_user.id,
        actor=authorized_user.username if authorized_user else None,
        after_summary=f"ui_user_unlocked username={unlocked_user.username}",
    )
    return RedirectResponse("/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/users/{user_id}/password")
async def admin_users_password_reset(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    authorized_user: Optional[User] = Depends(_enforce_ui_auth),
):
    """Reset a local user's password from the owner/admin browser UI."""
    _enforce_ui_role(authorized_user, "admin:manage_users")
    _enforce_csrf(request, csrf_token)
    try:
        updated_user = UserService.reset_password(db, user_id, new_password)
    except ValueError as exc:
        return _render_template(
            request,
            "admin_users.html",
            _users_context(db, error=str(exc)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    _record_ui_audit(
        db,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=updated_user.id,
        actor=authorized_user.username if authorized_user else None,
        after_summary=f"ui_user_password_reset username={updated_user.username}",
    )
    return RedirectResponse("/admin/users", status_code=status.HTTP_303_SEE_OTHER)
