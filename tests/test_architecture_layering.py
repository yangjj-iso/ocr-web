from pathlib import Path


def test_main_uses_v1_router_registry():
    content = Path("app/main.py").read_text(encoding="utf-8")
    assert "include_v1_routers(app)" in content
    assert "from app.interfaces.api.v1 import include_v1_routers" in content


def test_router_registry_includes_all_core_router_modules():
    content = Path("app/interfaces/api/v1/router_registry.py").read_text(encoding="utf-8")
    required_modules = [
        "include_business_routers",
        "include_ai_routers",
    ]
    for module in required_modules:
        assert module in content


def test_split_router_registries_are_defined():
    business_content = Path("app/interfaces/api/business/router_registry.py").read_text(encoding="utf-8")
    ai_content = Path("app/interfaces/api/ai/router_registry.py").read_text(encoding="utf-8")

    for module in ["auth_routes", "archives", "business_batches"]:
        assert module in business_content

    for module in ["tasks", "ai_batches", "qa", "evaluation", "files"]:
        assert module in ai_content


def test_api_modules_do_not_import_legacy_services_directly():
    for path in Path("app/api").glob("*.py"):
        if path.name in {"routes.py", "__init__.py"}:
            continue
        content = path.read_text(encoding="utf-8")
        assert "from app.services" not in content
        assert "import app.services" not in content


def test_feature_pages_use_src_alias_imports():
    for path in Path("frontend/src/features").rglob("*.vue"):
        content = path.read_text(encoding="utf-8")
        assert "from '../api/" not in content
        assert 'from "../api/' not in content
        assert "from '../../api/" not in content
        assert 'from "../../api/' not in content
        assert "from '../components/" not in content
        assert 'from "../components/' not in content
        assert "from '../composables/" not in content
        assert 'from "../composables/' not in content
        assert "from '../constants/" not in content
        assert 'from "../constants/' not in content


def test_shared_contracts_are_used_in_core_chains():
    field_service = Path("app/domains/extraction/field_service.py").read_text(encoding="utf-8")
    batch_ai_service = Path("app/domains/batch_ai/batch_ai_service.py").read_text(encoding="utf-8")
    qa_service = Path("app/domains/qa_eval/qa_service.py").read_text(encoding="utf-8")

    assert "FieldExtractionResult" in field_service
    assert "DocumentMergeGroup" in batch_ai_service
    assert "QaAnswerWithEvidence" in qa_service
