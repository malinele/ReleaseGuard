"""Static UI route regression tests.

These tests parse app/ui/routes.py without importing the FastAPI app. They
protect the readonly UI route contract from shape-only refactors that remove
existing routes while still satisfying weak TemplateResponse checks.
"""

import ast
from pathlib import Path


ROUTES_FILE = Path("app/ui/routes.py")

EXPECTED_ROUTES = {
    "root_dashboard": "/",
    "projects_list": "/projects",
    "evidence_dashboard": "/evidence",
    "project_detail": "/projects/{project_id}",
    "requirements_list": "/requirements",
    "requirement_detail": "/requirements/{requirement_id}",
    "proposal_detail": "/proposals/{proposal_id}",
    "traceability_view": "/traceability",
    "audit_view": "/audit",
}

EXPECTED_TEMPLATES = {
    "root_dashboard": "dashboard.html",
    "projects_list": "project_list.html",
    "evidence_dashboard": "evidence.html",
    "project_detail": "project_detail.html",
    "requirements_list": "requirement_list.html",
    "requirement_detail": "requirement_detail.html",
    "proposal_detail": "proposal_detail.html",
    "traceability_view": "traceability.html",
    "audit_view": "audit_log.html",
}


def _route_functions():
    tree = ast.parse(ROUTES_FILE.read_text(), filename=str(ROUTES_FILE))
    functions = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = node
    return functions


def _route_path(node):
    for decorator in node.decorator_list:
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "get"
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
        ):
            return decorator.args[0].value
    return None


def _template_response_call(node):
    calls = [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "TemplateResponse"
    ]
    assert len(calls) == 1, f"{node.name} must have exactly one TemplateResponse call"
    return calls[0]


def _template_name(call):
    assert len(call.args) >= 2, "TemplateResponse must use request-first positional form"
    assert isinstance(call.args[1], ast.Constant), "template name must be a string literal"
    return call.args[1].value


def _context_keys(call):
    assert len(call.args) >= 3, "TemplateResponse must pass context as the third positional argument"
    context = call.args[2]
    assert isinstance(context, ast.Dict), "TemplateResponse context must be a dict literal"
    return {
        key.value
        for key in context.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def test_expected_ui_routes_are_preserved():
    functions = _route_functions()
    actual = {name: _route_path(functions[name]) for name in EXPECTED_ROUTES if name in functions}
    assert actual == EXPECTED_ROUTES


def test_unsupported_audit_events_routes_are_absent():
    paths = {
        path
        for node in _route_functions().values()
        for path in [_route_path(node)]
        if path is not None
    }
    assert "/audit-events" not in paths
    assert "/audit-events/{event_id}" not in paths


def test_template_response_calls_use_request_first_signature():
    for name, node in _route_functions().items():
        if name not in EXPECTED_ROUTES:
            continue
        call = _template_response_call(node)
        assert call.args and isinstance(call.args[0], ast.Name)
        assert call.args[0].id == "request", f"{name} must pass request as first argument"
        assert "request" not in _context_keys(call), f"{name} must not include request in context"


def test_expected_templates_are_preserved():
    functions = _route_functions()
    actual = {
        name: _template_name(_template_response_call(functions[name]))
        for name in EXPECTED_TEMPLATES
    }
    assert actual == EXPECTED_TEMPLATES


def test_no_direct_starlette_template_response_imports():
    tree = ast.parse(ROUTES_FILE.read_text(), filename=str(ROUTES_FILE))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("starlette"):
            imported = {alias.name for alias in node.names}
            assert "TemplateResponse" not in imported
