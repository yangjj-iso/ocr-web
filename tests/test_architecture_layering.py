from pathlib import Path


def test_python_web_surface_is_ai_only():
    assert not Path("app/main.py").exists()
    assert not Path("app/main_business.py").exists()
    assert not Path("app/interfaces/api/v1/router_registry.py").exists()
    assert not Path("app/interfaces/api/business/router_registry.py").exists()


def test_main_ai_uses_ai_router_registry():
    content = Path("app/main_ai.py").read_text(encoding="utf-8")
    assert "include_ai_routers" in content
    assert "router_loader=include_ai_routers" in content


def test_compatibility_router_keeps_only_ai_modules():
    content = Path("app/api/routes.py").read_text(encoding="utf-8")
    for module in ["tasks_router", "ai_batches_router", "qa_router", "evaluation_router", "files_router"]:
        assert module in content
    for module in ["auth_router", "archives_router", "business_batches_router"]:
        assert module not in content


def test_api_modules_do_not_import_legacy_services_directly():
    for path in Path("app/api").glob("*.py"):
        if path.name in {"routes.py", "__init__.py"}:
            continue
        content = path.read_text(encoding="utf-8")
        assert "from app.services" not in content
        assert "import app.services" not in content


def test_frontend_next_uses_path_alias_imports():
    for path in Path("frontend-next/app").rglob("*.tsx"):
        content = path.read_text(encoding="utf-8")
        # Should use @/ alias, not relative paths to api/hooks/components
        assert "from '../api/" not in content
        assert 'from "../api/' not in content
        assert "from '../../api/" not in content
        assert 'from "../../api/' not in content


def test_shared_contracts_are_used_in_core_chains():
    field_service = Path("app/domains/extraction/field_service.py").read_text(encoding="utf-8")
    batch_ai_service = Path("app/domains/batch_ai/batch_ai_service.py").read_text(encoding="utf-8")
    qa_service = Path("app/domains/qa_eval/qa_service.py").read_text(encoding="utf-8")

    assert "FieldExtractionResult" in field_service
    assert "DocumentMergeGroup" in batch_ai_service
    assert "QaAnswerWithEvidence" in qa_service
