from dataclasses import dataclass
import logging
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import CodeChunkRecord, CodeFile, Project
from ...schemas.code import (
    CodeChunk,
    ProjectIngestionResult,
    RepositoryChunk,
    RepositoryFile,
    RepositoryFileError,
    RepositoryIngestionResponse,
    RepositoryStatistics,
    RepositorySummary,
)
from ..code_chunker import PythonCodeChunker
from ..code_upload import CodeUploadException, CodeUploadService
from ..embedding import EmbeddingService, EmbeddingServiceException


EXPECTED_EMBEDDING_DIMENSION = 384
logger = logging.getLogger(__name__)


@dataclass
class RepositoryIngestionException(Exception):
    code: str
    message: str
    status_code: int


class RepositoryIngestionService:
    def __init__(
        self,
        upload_service: CodeUploadService,
        python_chunker: PythonCodeChunker | None = None,
        embedding_service: EmbeddingService | None = None,
        max_files_per_batch: int = 50,
        max_total_upload_size_mb: int = 25,
        embedding_group_size: int = 8,
    ) -> None:
        self.upload_service = upload_service
        self.python_chunker = python_chunker or PythonCodeChunker()
        self.embedding_service = embedding_service
        self.max_files_per_batch = max_files_per_batch
        self.max_total_upload_size_bytes = max_total_upload_size_mb * 1024 * 1024
        self.embedding_group_size = embedding_group_size

    async def process(
        self,
        uploads: list[UploadFile] | None,
        session: AsyncSession | None = None,
        project_name: str | None = None,
    ) -> RepositoryIngestionResponse:
        response, _, _ = await self._run(uploads, session, project_name)
        return response

    async def ingest(
        self,
        project_name: str,
        uploads: list[UploadFile] | None,
        session: AsyncSession,
    ) -> ProjectIngestionResult:
        """Ingest a repository and persist its project, files, chunks, and embeddings."""
        if not isinstance(project_name, str) or not project_name.strip():
            raise RepositoryIngestionException(
                "INVALID_PROJECT_NAME", "A project name is required.", 422
            )

        response, project_id, embeddings_created = await self._run(
            uploads, session, project_name.strip()
        )
        return ProjectIngestionResult(
            project_id=project_id,
            project_name=project_name.strip(),
            files_processed=response.statistics.successful_files,
            files_failed=response.statistics.failed_files,
            chunks_created=response.statistics.total_chunks,
            embeddings_created=embeddings_created,
            errors=response.errors,
        )

    async def _run(
        self,
        uploads: list[UploadFile] | None,
        session: AsyncSession | None,
        project_name: str | None,
    ) -> tuple[RepositoryIngestionResponse, UUID | None, int]:
        if not uploads:
            raise RepositoryIngestionException(
                "EMPTY_BATCH", "At least one file is required.", 400
            )
        if len(uploads) > self.max_files_per_batch:
            raise RepositoryIngestionException(
                "TOO_MANY_FILES",
                f"A batch cannot contain more than {self.max_files_per_batch} files.",
                413,
            )

        logger.info("upload-batch validation starting file_count=%d", len(uploads))
        self._validate_total_upload_size(uploads)
        logger.info("upload-batch validation completed")
        files: list[RepositoryFile] = []
        chunks: list[RepositoryChunk] = []
        errors: list[RepositoryFileError] = []
        language_counts: dict[str, int] = {}
        total_lines = 0
        total_size_bytes = 0
        successful_files = 0
        embeddings_created = 0
        project: Project | None = None

        try:
            for upload in uploads:
                filename = upload.filename or "[missing]"
                logger.info(
                    "upload-batch reading file filename=%s size_bytes=%d",
                    filename,
                    self._upload_size(upload),
                )
                try:
                    metadata, source = await self.upload_service.read_source(
                        upload, preserve_filename=True
                    )
                except CodeUploadException as error:
                    logger.info("upload-batch file validation failed filename=%s code=%s", filename, error.code)
                    errors.append(self._error(filename, error))
                    continue
                logger.info(
                    "upload-batch file read filename=%s size_bytes=%d lines=%d",
                    metadata.filename,
                    metadata.size_bytes,
                    metadata.line_count,
                )

                total_lines += metadata.line_count
                total_size_bytes += metadata.size_bytes
                language_counts[metadata.language] = language_counts.get(
                    metadata.language, 0
                ) + 1

                if metadata.extension != ".py":
                    file_metadata = RepositoryFile(
                        filename=metadata.filename,
                        language=metadata.language,
                        extension=metadata.extension,
                        size_bytes=metadata.size_bytes,
                        line_count=metadata.line_count,
                        parser_status="not_implemented",
                        chunker_status="not_implemented",
                    )
                    files.append(file_metadata)
                    successful_files += 1
                    if session is not None:
                        project = await self._ensure_project(session, project, project_name)
                        await self._persist_file(session, project, file_metadata, [])
                    del source
                    continue

                try:
                    logger.info("upload-batch parsing and chunking filename=%s", metadata.filename)
                    result = self.python_chunker.chunk(source, metadata.filename)
                except ValueError as error:
                    files.append(
                        RepositoryFile(
                            filename=metadata.filename,
                            language=metadata.language,
                            extension=metadata.extension,
                            size_bytes=metadata.size_bytes,
                            line_count=metadata.line_count,
                            parser_status="error",
                            chunker_status="not_run",
                        )
                    )
                    errors.append(
                        RepositoryFileError(
                            filename=metadata.filename,
                            code="SYNTAX_ERROR",
                            message=str(error),
                        )
                    )
                    logger.info("upload-batch chunking failed filename=%s", metadata.filename)
                    del source
                    continue

                file_chunks = [self._repository_chunk(chunk) for chunk in result.chunks]
                logger.info(
                    "upload-batch chunking completed filename=%s chunk_count=%d",
                    metadata.filename,
                    len(result.chunks),
                )
                del source
                chunks.extend(file_chunks)
                file_metadata = RepositoryFile(
                    filename=metadata.filename,
                    language=metadata.language,
                    extension=metadata.extension,
                    size_bytes=metadata.size_bytes,
                    line_count=metadata.line_count,
                    chunk_count=len(file_chunks),
                    parser_status="completed",
                    chunker_status="completed",
                )
                files.append(file_metadata)
                successful_files += 1
                if session is not None:
                    project = await self._ensure_project(session, project, project_name)
                    embeddings_created += await self._persist_file(
                        session, project, file_metadata, result.chunks
                    )
                del result, file_chunks

            if session is not None and project is not None:
                logger.info("upload-batch final database commit starting")
                await session.commit()
                logger.info("upload-batch final database commit completed")
        except Exception:
            logger.exception("upload-batch pipeline failed")
            if session is not None:
                await session.rollback()
            raise

        response = RepositoryIngestionResponse(
            success=successful_files > 0,
            repository=RepositorySummary(file_count=len(files), chunk_count=len(chunks)),
            files=files,
            chunks=chunks,
            statistics=RepositoryStatistics(
                total_files=len(uploads),
                successful_files=successful_files,
                failed_files=len(errors),
                total_lines=total_lines,
                total_size_bytes=total_size_bytes,
                total_chunks=len(chunks),
                languages=language_counts,
            ),
            errors=errors,
        )
        return response, project.id if project is not None else None, embeddings_created

    async def _persist_file(
        self,
        session: AsyncSession,
        project: Project,
        file_metadata: RepositoryFile,
        source_chunks: list[CodeChunk],
    ) -> int:
        if self.embedding_service is None:
            raise RepositoryIngestionException(
                "EMBEDDING_NOT_CONFIGURED",
                "Embedding service is not configured for persistence.",
                503,
            )

        code_file = CodeFile(
            project_id=project.id,
            filename=file_metadata.filename,
            language=file_metadata.language or "unknown",
            extension=file_metadata.extension or "",
            size_bytes=file_metadata.size_bytes,
            line_count=file_metadata.line_count,
        )
        session.add(code_file)
        logger.info("upload-batch database file flush starting filename=%s", file_metadata.filename)
        await session.flush()
        logger.info("upload-batch database file flush completed filename=%s", file_metadata.filename)
        embeddings_created = 0
        for start in range(0, len(source_chunks), self.embedding_group_size):
            source_group = source_chunks[start : start + self.embedding_group_size]
            logger.info(
                "upload-batch embedding group starting filename=%s start=%d count=%d",
                file_metadata.filename,
                start,
                len(source_group),
            )
            try:
                embeddings = self.embedding_service.embed_chunks(source_group)
            except EmbeddingServiceException as error:
                raise RepositoryIngestionException(error.code, error.message, 503) from error
            if any(
                embedding.dimension != EXPECTED_EMBEDDING_DIMENSION
                or len(embedding.embedding) != EXPECTED_EMBEDDING_DIMENSION
                for embedding in embeddings
            ):
                raise RepositoryIngestionException(
                    "INVALID_EMBEDDING_DIMENSION",
                    "Chunk embeddings must have exactly 384 dimensions.",
                    422,
                )
            logger.info(
                "upload-batch embedding group completed filename=%s start=%d count=%d",
                file_metadata.filename,
                start,
                len(embeddings),
            )
            for source_chunk, embedding in zip(source_group, embeddings, strict=True):
                session.add(
                    CodeChunkRecord(
                        file_id=code_file.id,
                        chunk_id=source_chunk.chunk_id,
                        chunk_type=source_chunk.chunk_type,
                        name=source_chunk.name,
                        start_line=source_chunk.start_line,
                        end_line=source_chunk.end_line,
                        content=source_chunk.content,
                        language=source_chunk.language,
                        embedding=embedding.embedding,
                    )
                )
            logger.info(
                "upload-batch database flush starting filename=%s group_start=%d",
                file_metadata.filename,
                start,
            )
            await session.flush()
            logger.info(
                "upload-batch database flush completed filename=%s group_start=%d",
                file_metadata.filename,
                start,
            )
            embeddings_created += len(embeddings)
            del embeddings, source_group
        return embeddings_created

    async def _ensure_project(
        self,
        session: AsyncSession,
        project: Project | None,
        project_name: str | None,
    ) -> Project:
        if project is not None:
            return project
        project = Project(name=project_name or f"repository-{uuid4().hex[:12]}")
        session.add(project)
        logger.info("upload-batch database project flush starting")
        await session.flush()
        logger.info("upload-batch database project flush completed")
        return project

    def _validate_total_upload_size(self, uploads: list[UploadFile]) -> None:
        total_size = sum(self._upload_size(upload) for upload in uploads)
        if total_size > self.max_total_upload_size_bytes:
            raise RepositoryIngestionException(
                "BATCH_TOO_LARGE",
                "The uploaded files exceed the maximum total request size.",
                413,
            )

    @staticmethod
    def _upload_size(upload: UploadFile) -> int:
        upload.file.seek(0, 2)
        size_bytes = upload.file.tell()
        upload.file.seek(0)
        return size_bytes

    @staticmethod
    def _repository_chunk(chunk: CodeChunk) -> RepositoryChunk:
        return RepositoryChunk(
            chunk_id=chunk.chunk_id,
            filename=chunk.filename,
            language=chunk.language,
            chunk_type=chunk.chunk_type,
            name=chunk.name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            parent=chunk.parent,
            class_name=chunk.class_name,
            function_name=chunk.function_name,
        )

    @staticmethod
    def _error(filename: str, error: CodeUploadException) -> RepositoryFileError:
        return RepositoryFileError(
            filename=filename,
            code=error.code,
            message=error.message,
        )
