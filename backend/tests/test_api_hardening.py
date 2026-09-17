import asyncio

from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from app.main import app
from backend.app.agents import SecurityAgent
from backend.app.api.routes import health
from backend.app.core.config import Settings
from backend.app.services.gemini import GeminiService
from backend.app.services.rag import RAGService, RAGServiceException


client = TestClient(app)


def test_whitespace_query_returns_sanitized_validation_error() -> None:
    response = client.post("/api/v1/code/search", json={"query": "   "})

    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "The request contains invalid or missing values.",
        },
    }


def test_invalid_project_id_returns_sanitized_validation_error() -> None:
    response = client.post(
        "/api/v1/code/ask",
        json={"query": "find auth", "project_id": "not-a-uuid"},
    )

    assert response.status_code == 422
    assert "not-a-uuid" not in response.text
    assert "traceback" not in response.text.lower()


def test_readiness_returns_safe_database_failure(monkeypatch) -> None:
    monkeypatch.setattr(health, "engine", None)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "Required infrastructure is unavailable.",
        },
    }
    assert "DATABASE_URL" not in response.text


def test_oversized_upload_remains_structured_and_safe() -> None:
    response = client.post(
        "/api/v1/code/upload",
        files={"file": ("large.py", b"x" * (5 * 1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert "C:\\" not in response.text


def test_unsupported_upload_remains_structured() -> None:
    response = client.post(
        "/api/v1/code/upload",
        files={"file": ("archive.zip", b"data", "application/zip")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_security_headers_are_present() -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_cors_allows_configured_development_origin() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "*" not in response.headers["access-control-allow-origin"]


def test_cors_allows_production_frontend_origin_for_preflight(monkeypatch) -> None:
    cors_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )
    monkeypatch.setitem(
        cors_middleware.kwargs,
        "allow_origins",
        ["https://codepilot-ai-1-pjss.onrender.com"],
    )
    monkeypatch.setattr(app, "middleware_stack", None)

    response = client.options(
        "/api/v1/code/search",
        headers={
            "Origin": "https://codepilot-ai-1-pjss.onrender.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, authorization",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://codepilot-ai-1-pjss.onrender.com"
    )
    assert (
        response.headers["access-control-allow-methods"]
        == "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
    )
    assert (
        response.headers["access-control-allow-headers"]
        == "content-type, authorization"
    )


def test_production_settings_do_not_enable_debug_by_default() -> None:
    production = Settings(
        _env_file=None,
        APP_ENV="production",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://service:password@db.example.com/codepilot",
        GEMINI_API_KEY="test-only-key",
        CORS_ORIGINS=["https://app.example.com"],
    )

    assert production.DEBUG is False
    assert production.CORS_ORIGINS == ["https://app.example.com"]


def test_path_traversal_is_rejected_for_single_upload() -> None:
    response = client.post(
        "/api/v1/code/upload",
        files={"file": ("../outside.py", b"x = 1\n", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSAFE_FILENAME"


def test_review_agent_timeout_is_sanitized() -> None:
    class SlowGemini:
        timeout_seconds = 0.001

        def generate(self, prompt: str) -> str:
            import time

            time.sleep(0.05)
            return '{"findings": []}'

    async def run() -> None:
        result = await SecurityAgent(SlowGemini()).analyze("review", [])
        return result

    try:
        asyncio.run(run())
    except Exception as error:
        assert getattr(error, "code", None) == "GEMINI_TIMEOUT"
        assert "traceback" not in str(error).lower()
    else:
        raise AssertionError("Expected the review agent to time out")


def test_rag_timeout_is_structured() -> None:
    class SlowGemini:
        timeout_seconds = 0.001

        def generate(self, prompt: str) -> str:
            import time

            time.sleep(0.05)
            return "answer"

    class Search:
        async def search(self, *args, **kwargs):
            return [
                {
                    "filename": "safe.py",
                    "chunk_type": "module",
                    "name": "module",
                    "start_line": 1,
                    "end_line": 1,
                    "language": "python",
                    "similarity": 1.0,
                    "content": "value = 1",
                }
            ]

    async def run() -> None:
        await RAGService(Search(), SlowGemini()).ask(None, "query")

    try:
        asyncio.run(run())
    except RAGServiceException as error:
        assert error.code == "GEMINI_TIMEOUT"
        assert error.message == "The code assistant timed out while generating an answer."
    else:
        raise AssertionError("Expected RAG to time out")
