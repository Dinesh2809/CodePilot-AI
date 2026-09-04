from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from backend.app.api.routes import code_search
from backend.app.services.embedding import InMemoryEmbedding
from backend.app.services.semantic_search import (
    SemanticSearchException,
    SemanticSearchService,
)


client = TestClient(app)


class FakeEmbeddingService:
    model_name = "fake-model"

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self.embedded_queries: list[str] = []

    def embed_text(self, query: str) -> InMemoryEmbedding:
        self.embedded_queries.append(query)
        return InMemoryEmbedding("text", self.dimension, [0.1] * self.dimension)


class FakeResult:
    def __init__(self, rows: list[tuple[object, object, float]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[object, object, float]]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[tuple[object, object, float]]) -> None:
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.rows)


def make_row(distance: float = 0.15) -> tuple[object, object, float]:
    project_id = uuid4()
    file_id = uuid4()
    return (
        SimpleNamespace(
            chunk_id="auth.py:function:login",
            chunk_type="function",
            name="login",
            start_line=4,
            end_line=8,
            language="python",
            content="def login(user):\n    return authenticate(user)",
        ),
        SimpleNamespace(id=file_id, project_id=project_id, filename="src/auth.py"),
        distance,
    )


def test_semantic_search_returns_metadata_and_similarity() -> None:
    embedding_service = FakeEmbeddingService()
    session = FakeSession([make_row()])

    results = __import__("asyncio").run(
        SemanticSearchService(embedding_service).search(
            session, "where is authentication", top_k=5
        )
    )

    assert len(embedding_service.embedded_queries) == 1
    assert len(embedding_service.embed_text("query").embedding) == 384
    assert results[0]["filename"] == "src/auth.py"
    assert results[0]["similarity"] == 0.85


def test_semantic_search_rejects_incorrect_embedding_dimension() -> None:
    import asyncio

    try:
        asyncio.run(
            SemanticSearchService(FakeEmbeddingService(3)).search(
                FakeSession([]), "query"
            )
        )
    except SemanticSearchException as error:
        assert error.code == "INVALID_EMBEDDING_DIMENSION"
    else:
        raise AssertionError("Expected an incorrect embedding dimension to fail")


def test_semantic_search_applies_top_k_and_project_filter() -> None:
    session = FakeSession([])
    project_id = uuid4()

    __import__("asyncio").run(
        SemanticSearchService(FakeEmbeddingService()).search(
            session, "query", top_k=2, project_id=project_id
        )
    )

    assert session.statement is not None
    assert session.statement._limit_clause.value == 2
    assert len(session.statement._where_criteria) == 1


def test_search_endpoint_validates_empty_query_and_top_k() -> None:
    response = client.post("/api/v1/code/search", json={"query": "", "top_k": 0})

    assert response.status_code == 422


def test_search_endpoint_returns_no_results(monkeypatch) -> None:
    session = FakeSession([])
    service = SemanticSearchService(FakeEmbeddingService())
    monkeypatch.setattr(code_search, "semantic_search_service", service)
    app.dependency_overrides[code_search.get_db_session] = lambda: session
    try:
        response = client.post(
            "/api/v1/code/search", json={"query": "missing symbol", "top_k": 3}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "query": "missing symbol",
        "results": [],
        "result_count": 0,
    }


def test_search_endpoint_returns_result(monkeypatch) -> None:
    monkeypatch.setattr(
        code_search,
        "semantic_search_service",
        SemanticSearchService(FakeEmbeddingService()),
    )
    session = FakeSession([make_row(0.2)])
    app.dependency_overrides[code_search.get_db_session] = lambda: session
    try:
        response = client.post(
            "/api/v1/code/search", json={"query": "authentication", "top_k": 1}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["result_count"] == 1
    assert body["results"][0]["similarity"] == 0.8