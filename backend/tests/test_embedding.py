import math

from fastapi.testclient import TestClient

from app.main import app
from backend.app.api.routes import code_embed
from app.schemas.code import CodeChunk
from app.services.embedding import EmbeddingService, EmbeddingServiceException


client = TestClient(app)


def make_chunk(chunk_id: str, content: str) -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        filename="example.py",
        language="python",
        chunk_type="function",
        name=chunk_id,
        start_line=1,
        end_line=1,
        content=content,
    )


class FakeModel:
    def __init__(self) -> None:
        self.calls = 0
        self.last_texts: list[str] = []

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts: list[str], **_: object) -> list[list[float]]:
        self.calls += 1
        self.last_texts = texts
        vectors = []
        for text in texts:
            vector = [float(len(text)), float(sum(ord(char) for char in text) % 97), 1.0]
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / norm for value in vector])
        return vectors


def service_with_fake_model() -> tuple[EmbeddingService, FakeModel]:
    model = FakeModel()
    return EmbeddingService("fake-model", lambda _: model), model


def test_single_text_embedding_has_dimension_and_normalization() -> None:
    service, _ = service_with_fake_model()

    result = service.embed_text("def login(): pass")

    assert result.chunk_id == "text"
    assert result.dimension == 3
    assert len(result.embedding) == 3
    assert math.isclose(math.sqrt(sum(value * value for value in result.embedding)), 1.0)


def test_multiple_chunks_are_batched_and_ordered() -> None:
    service, model = service_with_fake_model()
    chunks = [make_chunk("first", "alpha"), make_chunk("second", "beta")]

    results = service.embed_chunks(chunks)

    assert [result.chunk_id for result in results] == ["first", "second"]
    assert model.calls == 1
    assert model.last_texts == ["alpha", "beta"]


def test_empty_text_and_empty_chunk_list() -> None:
    service, _ = service_with_fake_model()

    assert service.embed_chunks([]) == []
    try:
        service.embed_text("   ")
    except EmbeddingServiceException as error:
        assert error.code == "EMPTY_TEXT"
    else:
        raise AssertionError("Expected empty text to be rejected")


def test_same_text_is_consistent_and_different_text_differs() -> None:
    service, _ = service_with_fake_model()

    first = service.embed_text("same").embedding
    second = service.embed_text("same").embedding
    different = service.embed_text("different").embedding

    assert first == second
    assert first != different


def test_model_is_loaded_once_and_reused() -> None:
    created: list[FakeModel] = []

    def factory(_: str) -> FakeModel:
        model = FakeModel()
        created.append(model)
        return model

    service = EmbeddingService("fake-model", factory)
    service.embed_text("first")
    service.embed_text("second")

    assert len(created) == 1
    assert created[0].calls == 2


def test_model_loading_failure_is_structured() -> None:
    def failing_factory(_: str) -> FakeModel:
        raise RuntimeError("model unavailable")

    service = EmbeddingService("unavailable", failing_factory)

    try:
        service.embed_text("text")
    except EmbeddingServiceException as error:
        assert error.code == "MODEL_LOAD_FAILED"
    else:
        raise AssertionError("Expected model loading failure")


def test_embedding_endpoint_chunks_python_and_returns_metadata_only(monkeypatch) -> None:
    service, _ = service_with_fake_model()
    monkeypatch.setattr(code_embed, "embedding_service", service)

    response = client.post(
        "/api/v1/code/embed",
        files={
            "files": (
                "example_codepilot.py",
                b"def calculate_discount(price, discount):\n    return price - discount\n",
                "text/x-python",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["embedding_model"] == "fake-model"
    assert body["embedding_dimension"] == 3
    assert len(body["chunks"]) == 1
    assert body["chunks"][0]["dimension"] == 3
    assert "embedding" not in body["chunks"][0]


def test_embedding_endpoint_reports_unsupported_files(monkeypatch) -> None:
    service, _ = service_with_fake_model()
    monkeypatch.setattr(code_embed, "embedding_service", service)

    response = client.post(
        "/api/v1/code/embed",
        files={"files": ("script.js", b"const value = 1;", "text/javascript")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "PARSER_NOT_IMPLEMENTED"
