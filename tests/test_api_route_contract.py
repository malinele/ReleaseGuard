"""Static API route regression tests for ReleaseGuard.

These tests parse API route source files without importing the FastAPI app.
They protect the readonly API route contracts from refactors that could
break route ordering, response schemas, or path declarations.
"""

import ast
from pathlib import Path


ROUTES_FILE = Path("app/api/audit.py")


def _parse_audit_routes():
    """Parse audit.py and extract all @router decorator paths in order."""
    tree = ast.parse(ROUTES_FILE.read_text(), filename=str(ROUTES_FILE))
    routes = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in ("get", "post", "put", "delete", "patch")
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                ):
                    route_path = decorator.args[0].value
                    routes.append((node.name, route_path))
    return routes


def test_audit_export_route_before_dynamic_route():
    """Assert /api/audit/export is declared before /api/audit/{audit_id}.

    FastAPI routes are matched in declaration order. Export must be
    defined before the dynamic {audit_id} pattern to avoid shadowing.
    """
    routes = _parse_audit_routes()
    route_paths = [path for _, path in routes]

    export_idx = None
    dynamic_idx = None

    for idx, path in enumerate(route_paths):
        if path == "/export":
            export_idx = idx
        elif "{audit_id}" in path or path == "/{audit_id}":
            dynamic_idx = idx

    assert export_idx is not None, (
        "/api/audit/export route not found in audit.py"
    )
    assert dynamic_idx is not None, (
        "/api/audit/{audit_id} route not found in audit.py"
    )
    assert export_idx < dynamic_idx, (
        f"/api/audit/export (index {export_idx}) must be declared before "
        f"/api/audit/{{audit_id}} (index {dynamic_idx})"
    )


def test_audit_export_response_schema_names_exist():
    """Assert AuditExportFilters, AuditExportSummary, AuditExportResponse exist.

    These schema names are imported by audit.py and used in route
    response_model declarations. Removing them would break the API contract.
    """
    schema_file = Path("app/schemas/audit.py")
    assert schema_file.exists(), "app/schemas/audit.py not found"

    content = schema_file.read_text()

    required_names = [
        "AuditExportFilters",
        "AuditExportSummary",
        "AuditExportResponse",
    ]

    for name in required_names:
        assert name in content, (
            f"Schema class '{name}' not found in app/schemas/audit.py. "
            f"This name is imported by audit.py and required for the export endpoint."
        )
