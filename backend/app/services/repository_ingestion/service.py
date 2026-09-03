from dataclasses import dataclass

from fastapi import UploadFile

from ...schemas.code import (
    CodeChunk,
    RepositoryChunk,
    RepositoryFile,
    RepositoryFileError,
    RepositoryIngestionResponse,
    RepositoryStatistics,
    RepositorySummary,
)
from ..code_chunker import PythonCodeChunker
from ..code_upload import CodeUploadException, CodeUploadService


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
        max_files_per_batch: int = 50,
    ) -> None:
        self.upload_service = upload_service
        self.python_chunker = python_chunker or PythonCodeChunker()
        self.max_files_per_batch = max_files_per_batch

    async def process(
        self, uploads: list[UploadFile] | None
    ) -> RepositoryIngestionResponse:
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

        files: list[RepositoryFile] = []
        chunks: list[RepositoryChunk] = []
        errors: list[RepositoryFileError] = []
        language_counts: dict[str, int] = {}
        total_lines = 0
        total_size_bytes = 0
        successful_files = 0

        for upload in uploads:
            filename = upload.filename or "[missing]"
            try:
                metadata, source = await self.upload_service.read_source(
                    upload, preserve_filename=True
                )
            except CodeUploadException as error:
                errors.append(self._error(filename, error))
                continue

            total_lines += metadata.line_count
            total_size_bytes += metadata.size_bytes
            language_counts[metadata.language] = language_counts.get(metadata.language, 0) + 1

            if metadata.extension != ".py":
                files.append(
                    RepositoryFile(
                        filename=metadata.filename,
                        language=metadata.language,
                        extension=metadata.extension,
                        size_bytes=metadata.size_bytes,
                        line_count=metadata.line_count,
                        parser_status="not_implemented",
                        chunker_status="not_implemented",
                    )
                )
                successful_files += 1
                continue

            try:
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
                continue

            file_chunks = [self._repository_chunk(chunk) for chunk in result.chunks]
            chunks.extend(file_chunks)
            files.append(
                RepositoryFile(
                    filename=metadata.filename,
                    language=metadata.language,
                    extension=metadata.extension,
                    size_bytes=metadata.size_bytes,
                    line_count=metadata.line_count,
                    chunk_count=len(file_chunks),
                    parser_status="completed",
                    chunker_status="completed",
                )
            )
            successful_files += 1

        statistics = RepositoryStatistics(
            total_files=len(uploads),
            successful_files=successful_files,
            failed_files=len(errors),
            total_lines=total_lines,
            total_size_bytes=total_size_bytes,
            total_chunks=len(chunks),
            languages=language_counts,
        )
        return RepositoryIngestionResponse(
            success=successful_files > 0,
            repository=RepositorySummary(
                file_count=len(files), chunk_count=len(chunks)
            ),
            files=files,
            chunks=chunks,
            statistics=statistics,
            errors=errors,
        )

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
