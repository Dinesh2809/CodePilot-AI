from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CodeChunkRecord, CodeFile
from .embedding import EmbeddingService, EmbeddingServiceException


EXPECTED_EMBEDDING_DIMENSION = 384


@dataclass
class SemanticSearchException(Exception):
    code: str
    message: str


class SemanticSearchService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        expected_dimension: int = EXPECTED_EMBEDDING_DIMENSION,
    ) -> None:
        self.embedding_service = embedding_service
        self.expected_dimension = expected_dimension

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        project_id: UUID | None = None,
    ) -> list[dict[str, object]]:
        try:
            query_embedding = self.embedding_service.embed_text(query)
        except EmbeddingServiceException as error:
            raise SemanticSearchException(error.code, error.message) from error

        if query_embedding.dimension != self.expected_dimension or len(query_embedding.embedding) != self.expected_dimension:
            raise SemanticSearchException(
                "INVALID_EMBEDDING_DIMENSION",
                f"Query embedding must have exactly {self.expected_dimension} dimensions.",
            )

        distance = CodeChunkRecord.embedding.cosine_distance(query_embedding.embedding)
        statement: Select[tuple[CodeChunkRecord, CodeFile, float]] = (
            select(CodeChunkRecord, CodeFile, distance.label("distance"))
            .join(CodeFile, CodeChunkRecord.file_id == CodeFile.id)
            .order_by(distance)
            .limit(top_k)
        )
        if project_id is not None:
            statement = statement.where(CodeFile.project_id == project_id)

        try:
            result = await session.execute(statement)
        except Exception as error:
            raise SemanticSearchException(
                "SEARCH_FAILED", "Unable to search code chunks."
            ) from error

        return [
            {
                "project_id": file.project_id,
                "file_id": file.id,
                "filename": file.filename,
                "chunk_id": chunk.chunk_id,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": chunk.language,
                "content": chunk.content,
                "similarity": max(0.0, min(1.0, 1.0 - float(distance_value))),
            }
            for chunk, file, distance_value in result.all()
        ]