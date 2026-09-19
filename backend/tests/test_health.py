from fastapi.testclient import TestClient

from app.main import app
from backend.app.api.routes import health

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_returns_safe_database_failure() -> None:
    class FailingSession:
        async def execute(self, query) -> None:
            raise RuntimeError("database connection failed")

    async def failing_database():
        yield FailingSession()

    app.dependency_overrides[health.get_db] = failing_database
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "Required infrastructure is unavailable.",
        },
    }
