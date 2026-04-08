from app.main_ai import app as ai_app
from app.main_business import app as business_app


def _paths(app):
    return {route.path for route in app.routes}


def test_business_app_exposes_business_routes_only():
    paths = _paths(business_app)

    assert "/api/auth/login" in paths
    assert "/api/ocr/archive-records" in paths
    assert "/api/ocr/scan-folder" in paths
    assert "/api/ocr/tasks" not in paths
    assert "/api/ocr/batches/{batch_id}/qa" not in paths


def test_ai_app_exposes_ai_routes_only():
    paths = _paths(ai_app)

    assert "/api/ocr/tasks" in paths
    assert "/api/ocr/batches/{batch_id}/boundary-analysis" in paths
    assert "/api/ocr/batches/{batch_id}/boundary-truth" in paths
    assert "/api/ocr/batches/{batch_id}/qa" in paths
    assert "/api/ocr/archive-records" not in paths
    assert "/api/auth/login" not in paths
