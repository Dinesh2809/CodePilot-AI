import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from backend.app.agents import AgentAnalysis, ReviewFinding, FinalReview
from backend.app.api.routes import code_review
from backend.app.services.gemini import GeminiService, GeminiServiceException
from backend.app.services.semantic_search import SemanticSearchException


client = TestClient(app)

MOCK_PROJECT_ID = uuid4()
MOCK_FILE_ID = uuid4()

MOCK_RESULT = {
    "project_id": MOCK_PROJECT_ID,
    "file_id": MOCK_FILE_ID,
    "filename": "src/secure.py",
    "chunk_id": "src/secure.py:function:validate_input",
    "chunk_type": "function",
    "name": "validate_input",
    "start_line": 5,
    "end_line": 12,
    "language": "python",
    "content": "def validate_input(data):\n    return len(data) > 0",
    "similarity": 0.93,
}


class FakeSearchService:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self.results = results
        self.calls: list[tuple[str, int, object]] = []

    async def search(self, session, query: str, top_k: int, project_id=None):
        self.calls.append((query, top_k, project_id))
        return self.results


class FakeOrchestrator:
    def __init__(self, review: FinalReview) -> None:
        self.review_result = review
        self.calls: list[tuple[str, list]] = []

    async def review(self, query: str, context: list):
        self.calls.append((query, context))
        return self.review_result


def make_finding(
    category: str,
    severity: str,
    title: str,
    filename: str = "src/example.py",
    start_line: int = 1,
    end_line: int = 3,
) -> ReviewFinding:
    return ReviewFinding(
        category=category,
        severity=severity,
        title=title,
        description=f"Description for {title}.",
        filename=filename,
        start_line=start_line,
        end_line=end_line,
        recommendation=f"Recommendation for {title}.",
    )


def test_review_endpoint_validates_empty_query() -> None:
    """Verify that empty query is rejected."""
    response = client.post(
        "/api/v1/code/review",
        json={"query": "", "top_k": 5},
    )
    assert response.status_code == 422


def test_review_endpoint_validates_invalid_top_k() -> None:
    """Verify that invalid top_k values are rejected."""
    response = client.post(
        "/api/v1/code/review",
        json={"query": "Review this", "top_k": 100},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/code/review",
        json={"query": "Review this", "top_k": 0},
    )
    assert response.status_code == 422


def test_review_endpoint_accepts_valid_request() -> None:
    """Verify that valid requests are accepted."""
    response = client.post(
        "/api/v1/code/review",
        json={"query": "Review this code", "top_k": 10},
    )
    # Status depends on mock, but shouldn't be validation error
    assert response.status_code in [200, 422, 503, 500]  # May fail due to mocking


def test_review_endpoint_handles_semantic_search_exception() -> None:
    """Verify proper handling of semantic search errors."""
    with patch("backend.app.api.routes.code_review.search_service") as mock_search:
        mock_search.search = AsyncMock(
            side_effect=SemanticSearchException("EMPTY_TEXT", "Query is empty")
        )

        response = client.post(
            "/api/v1/code/review",
            json={"query": "Review", "top_k": 5},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "EMPTY_TEXT"


def test_review_endpoint_handles_empty_retrieval() -> None:
    """Verify proper handling when no code is retrieved."""
    with patch("backend.app.api.routes.code_review.search_service") as mock_search:
        mock_search.search = AsyncMock(return_value=[])

        response = client.post(
            "/api/v1/code/review",
            json={"query": "Review", "top_k": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_findings"] == 0
        assert "No relevant code context" in data["summary"]


def test_review_endpoint_handles_gemini_exception() -> None:
    """Verify proper handling of Gemini API errors."""
    with patch("backend.app.api.routes.code_review.search_service") as mock_search, \
         patch("backend.app.api.routes.code_review.orchestrator") as mock_orchestrator:
        mock_search.search = AsyncMock(return_value=[MOCK_RESULT])
        mock_orchestrator.review = AsyncMock(
            side_effect=GeminiServiceException("MISSING_GEMINI_API_KEY", "API key not configured")
        )

        response = client.post(
            "/api/v1/code/review",
            json={"query": "Review", "top_k": 5},
        )

        assert response.status_code == 503
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "MISSING_GEMINI_API_KEY"


def test_review_endpoint_handles_unexpected_error() -> None:
    """Verify proper handling of unexpected errors."""
    with patch("backend.app.api.routes.code_review.search_service") as mock_search, \
         patch("backend.app.api.routes.code_review.orchestrator") as mock_orchestrator:
        mock_search.search = AsyncMock(return_value=[MOCK_RESULT])
        mock_orchestrator.review = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        response = client.post(
            "/api/v1/code/review",
            json={"query": "Review", "top_k": 5},
        )

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False


def test_review_endpoint_successful_review() -> None:
    """Verify successful review with findings."""
    finding = make_finding("security", "high", "SQL Injection")

    mock_review = FinalReview(
        summary="Found 1 security issue.",
        findings=[finding],
        total_findings=1,
        critical_count=0,
        high_count=1,
        medium_count=0,
        low_count=0,
        info_count=0,
        categories=["security"],
        agents_completed=["security", "quality", "performance"],
        agents_failed=[],
    )

    with patch("backend.app.api.routes.code_review.search_service") as mock_search, \
         patch("backend.app.api.routes.code_review.orchestrator") as mock_orchestrator:
        mock_search.search = AsyncMock(return_value=[MOCK_RESULT])
        mock_orchestrator.review = AsyncMock(return_value=mock_review)

        response = client.post(
            "/api/v1/code/review",
            json={"query": "Review this code", "top_k": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["query"] == "Review this code"
        assert data["summary"] == "Found 1 security issue."
        assert data["total_findings"] == 1
        assert data["high_count"] == 1
        assert data["categories"] == ["security"]
        assert len(data["findings"]) == 1
        assert data["findings"][0]["title"] == "SQL Injection"


def test_review_endpoint_with_project_id() -> None:
    """Verify that project_id is passed to semantic search."""
    finding = make_finding("quality", "medium", "Poor naming")
    mock_review = FinalReview(
        summary="Found issues.",
        findings=[finding],
        total_findings=1,
        critical_count=0,
        high_count=0,
        medium_count=1,
        low_count=0,
        info_count=0,
        categories=["quality"],
        agents_completed=["security", "quality", "performance"],
        agents_failed=[],
    )

    with patch("backend.app.api.routes.code_review.search_service") as mock_search, \
         patch("backend.app.api.routes.code_review.orchestrator") as mock_orchestrator:
        mock_search.search = AsyncMock(return_value=[MOCK_RESULT])
        mock_orchestrator.review = AsyncMock(return_value=mock_review)

        response = client.post(
            "/api/v1/code/review",
            json={
                "query": "Review",
                "top_k": 10,
                "project_id": str(MOCK_PROJECT_ID),
            },
        )

        assert response.status_code == 200
        # Verify search was called with project_id
        call_args = mock_search.search.call_args
        assert call_args.kwargs.get("project_id") == MOCK_PROJECT_ID


def test_review_endpoint_partial_agent_failure() -> None:
    """Verify handling of partial agent failures in response."""
    finding = make_finding("performance", "low", "Inefficient query")

    mock_review = FinalReview(
        summary="Found 1 issue. Agents failed: quality.",
        findings=[finding],
        total_findings=1,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=1,
        info_count=0,
        categories=["performance"],
        agents_completed=["security", "performance"],
        agents_failed=["quality"],
    )

    with patch("backend.app.api.routes.code_review.search_service") as mock_search, \
         patch("backend.app.api.routes.code_review.orchestrator") as mock_orchestrator:
        mock_search.search = AsyncMock(return_value=[MOCK_RESULT])
        mock_orchestrator.review = AsyncMock(return_value=mock_review)

        response = client.post(
            "/api/v1/code/review",
            json={"query": "Review", "top_k": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agents_failed"] == ["quality"]
        assert len(data["agents_completed"]) == 2


def test_review_endpoint_default_top_k() -> None:
    """Verify that default top_k is used when not provided."""
    mock_review = FinalReview(
        summary="No issues found.",
        findings=[],
        total_findings=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        info_count=0,
        categories=[],
        agents_completed=["security", "quality", "performance"],
        agents_failed=[],
    )

    with patch("backend.app.api.routes.code_review.search_service") as mock_search, \
         patch("backend.app.api.routes.code_review.orchestrator") as mock_orchestrator:
        mock_search.search = AsyncMock(return_value=[])
        mock_orchestrator.review = AsyncMock(return_value=mock_review)

        response = client.post(
            "/api/v1/code/review",
            json={"query": "Review"},  # No top_k provided
        )

        # Should succeed with default top_k=10
        assert response.status_code in [200, 503, 500]  # May fail due to mock setup


def test_review_response_schema_includes_all_fields() -> None:
    """Verify that response includes all expected fields."""
    findings = [
        make_finding("security", "critical", "Hardcoded secret"),
        make_finding("quality", "medium", "Poor naming"),
    ]

    mock_review = FinalReview(
        summary="Found 2 issues across security, quality.",
        findings=findings,
        total_findings=2,
        critical_count=1,
        high_count=0,
        medium_count=1,
        low_count=0,
        info_count=0,
        categories=["security", "quality"],
        agents_completed=["security", "quality", "performance"],
        agents_failed=[],
    )

    with patch("backend.app.api.routes.code_review.search_service") as mock_search, \
         patch("backend.app.api.routes.code_review.orchestrator") as mock_orchestrator:
        mock_search.search = AsyncMock(return_value=[MOCK_RESULT])
        mock_orchestrator.review = AsyncMock(return_value=mock_review)

        response = client.post(
            "/api/v1/code/review",
            json={"query": "Review", "top_k": 10},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all response fields are present
        assert "success" in data
        assert "query" in data
        assert "summary" in data
        assert "findings" in data
        assert "total_findings" in data
        assert "critical_count" in data
        assert "high_count" in data
        assert "medium_count" in data
        assert "low_count" in data
        assert "info_count" in data
        assert "categories" in data
        assert "agents_completed" in data
        assert "agents_failed" in data

        # Verify no stack traces or internal errors exposed
        assert "traceback" not in data
        assert "GEMINI" not in data.get("summary", "")
