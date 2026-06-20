from ai_suite.main import app


def test_core_routes_exist():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/health" in paths
    assert "/readiness" in paths
    assert "/api/v1/suite/status" in paths
    assert "/api/v1/workflows/health" in paths
    assert "/api/v1/bio-scout/health" in paths
    assert "/api/scrape" in paths
    assert "/api/upload" in paths
    assert "/api/v1/shipgate/health" in paths
    assert "/api/v1/shipgate/upload" in paths
