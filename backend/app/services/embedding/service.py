from dataclasses import dataclass
import logging
from typing import Any, Callable

from backend.app.schemas.code import CodeChunk


logger = logging.getLogger(__name__)


@dataclass
class EmbeddingServiceException(Exception):
    code: str
    message: str


@dataclass
class InMemoryEmbedding:
    chunk_id: str
    dimension: int
    embedding: list[float]


class EmbeddingService:
    def __init__(
        self,
        model_name: str,
        model_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self._model_factory = model_factory or self._create_model
        self._model: Any | None = None
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        self._ensure_model()
        assert self._dimension is not None
        return self._dimension

    def embed_text(self, text: str) -> InMemoryEmbedding:
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingServiceException("EMPTY_TEXT", "Text to embed cannot be empty.")
        return self.embed_chunks([CodeChunk(
            chunk_id="text",
            filename="",
            language="",
            chunk_type="text",
            name="text",
            start_line=1,
            end_line=1,
            content=text,
        )])[0]

    def embed_chunks(self, chunks: list[CodeChunk]) -> list[InMemoryEmbedding]:
        if not chunks:
            return []
        if any(not isinstance(chunk.content, str) or not chunk.content.strip() for chunk in chunks):
            raise EmbeddingServiceException(
                "EMPTY_TEXT", "Every chunk must contain non-empty text."
            )

        model = self._ensure_model()
        try:
            vectors = model.encode(
                [chunk.content for chunk in chunks],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as error:
            raise EmbeddingServiceException(
                "EMBEDDING_FAILED", "Unable to generate embeddings."
            ) from error

        logger.info(
            "Embedded chunks: model=%s count=%d dimension=%d",
            self.model_name,
            len(chunks),
            self.dimension,
        )

        return [
            InMemoryEmbedding(
                chunk_id=chunk.chunk_id,
                dimension=self.dimension,
                embedding=[float(value) for value in vector],
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            self._model = self._model_factory(self.model_name)
            self._dimension = int(self._model.get_sentence_embedding_dimension())
            logger.info(
                "Embedding model initialized: model=%s dimension=%d",
                self.model_name,
                self._dimension,
            )
        except Exception as error:
            raise EmbeddingServiceException(
                "MODEL_LOAD_FAILED", "Unable to load the embedding model."
            ) from error
        return self._model

    @staticmethod
    def _create_model(model_name: str) -> Any:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name)