"""Architecture layering tests — verify the flat API → services structure."""

from pathlib import Path


def test_python_web_surface_is_ai_only():
    """Ensure old multi-surface entry points are gone."""
    assert not Path("app/main.py").exists()
    assert not Path("app/main_business.py").exists()
    assert not Path("app/interfaces/api/v1/router_registry.py").exists()
    assert not Path("app/interfaces/api/business/router_registry.py").exists()


def test_old_abstraction_layers_removed():
    """Ensure the domains and workflows layers are gone."""
    assert not Path("app/application").exists()
    assert not Path("app/domains").exists()
    assert not Path("app/interfaces").exists()


def test_main_ai_uses_api_routes():
    content = Path("app/main_ai.py").read_text(encoding="utf-8")
    assert "include_ai_routers" in content
    assert "from app.api.routes" in content


def test_compatibility_router_keeps_only_ai_modules():
    content = Path("app/api/routes.py").read_text(encoding="utf-8")
    for module in ["tasks_router", "ai_batches_router", "qa_router", "evaluation_router", "files_router"]:
        assert module in content
    for module in ["auth_router", "archives_router", "business_batches_router"]:
        assert module not in content


def test_api_modules_do_not_import_deleted_layers():
    """API routes should not import from the deleted application/domains/interfaces layers."""
    for path in Path("app/api").glob("*.py"):
        if path.name in {"routes.py", "__init__.py"}:
            continue
        content = path.read_text(encoding="utf-8")
        assert "from app.application" not in content, f"{path.name} imports from deleted app.application"
        assert "from app.domains" not in content, f"{path.name} imports from deleted app.domains"
        assert "from app.interfaces" not in content, f"{path.name} imports from deleted app.interfaces"


def test_frontend_next_uses_path_alias_imports():
    for path in Path("frontend-next/app").rglob("*.tsx"):
        content = path.read_text(encoding="utf-8")
        assert "from '../api/" not in content
        assert 'from "../api/' not in content
        assert "from '../../api/" not in content
        assert 'from "../../api/' not in content
