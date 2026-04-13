from app.main_ai import app as ai_app


def _paths(app):
    return {route.path for route in app.routes}


def test_ai_app_exposes_ai_routes_only():
    paths = _paths(ai_app)

    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "/api/ocr/tasks" in paths
    assert "/api/archive/tasks" in paths
    assert "/api/archive/batches/{batch_id}/docs" in paths
    assert "/api/ocr/batches/{batch_id}/boundary-analysis" in paths
    assert "/api/ocr/batches/{batch_id}/boundary-truth" in paths
    assert "/api/ocr/batches/{batch_id}/qa" in paths
    assert "/api/ocr/archive-records" not in paths
    assert "/api/archive/tasks/my-assigned" not in paths
    assert "/api/archive/tasks/assign" not in paths
    assert "/api/archive/archive-records" not in paths
    assert "/api/archive/archive-records/{record_id}" not in paths
    assert "/api/archive/archive-records/{record_id}/pdf" not in paths
    assert "/api/archive/rework-tasks" not in paths
    assert "/api/archive/audit-logs" not in paths
    assert "/api/admin/users" not in paths
    assert "/api/auth/login" not in paths
    assert "/api/tenants" not in paths
    assert "/api/ocr/scan-folder" not in paths
