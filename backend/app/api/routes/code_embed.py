from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.schemas.code import (
    CodeUploadError,
    EmbeddingMetadata,
    EmbeddingResponse,
    RepositoryFileError,
)
from backend.app.services.code_chunker import PythonCodeChunker
from backend.app.services.code_upload import CodeUploadException, CodeUploadService
from backend.app.services.embedding import EmbeddingService, EmbeddingServiceException


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/code", tags=["code"])
upload_service = CodeUploadService(settings.MAX_UPLOAD_SIZE_MB)
python_chunker = PythonCodeChunker()
embedding_service = EmbeddingService(settings.EMBEDDING_MODEL)


@router.post(
    "/embed",
    response_model=EmbeddingResponse,
    response_model_exclude_none=True,
)
async def embed_code(
    files: list[UploadFile] = File(default=[]),
) -> EmbeddingResponse:
    if not files:
        return JSONResponse(
            status_code=400,
            content=EmbeddingResponse(
                success=False,
                embedding_model=embedding_service.model_name,
                error=CodeUploadError(code="EMPTY_BATCH", message="At least one file is required."),
            ).model_dump(exclude_none=True),
        )

    source_chunks = []
    errors: list[RepositoryFileError] = []
    for upload in files:
        filename = upload.filename or "[missing]"
        try:
            metadata, source = await upload_service.read_source(upload)
        except CodeUploadException as error:
            errors.append(
                RepositoryFileError(filename=filename, code=error.code, message=error.message)
            )
            continue

        if metadata.extension != ".py":
            errors.append(
                RepositoryFileError(
                    filename=metadata.filename,
                    code="PARSER_NOT_IMPLEMENTED",
                    message="Embedding is currently supported only for Python files.",
                )
            )
            continue

        try:
            source_chunks.extend(python_chunker.chunk(source, metadata.filename).chunks)
        except ValueError as error:
            errors.append(
                RepositoryFileError(
                    filename=metadata.filename, code="SYNTAX_ERROR", message=str(error)
                )
            )

    if not source_chunks:
        return EmbeddingResponse(
            success=False,
            embedding_model=embedding_service.model_name,
            errors=errors,
        )

    try:
        embeddings = embedding_service.embed_chunks(source_chunks)
    except EmbeddingServiceException as error:
        return JSONResponse(
            status_code=503 if error.code == "MODEL_LOAD_FAILED" else 422,
            content=EmbeddingResponse(
                success=False,
                embedding_model=embedding_service.model_name,
                errors=errors,
                error=CodeUploadError(code=error.code, message=error.message),
            ).model_dump(exclude_none=True),
        )

    return EmbeddingResponse(
        success=True,
        embedding_model=embedding_service.model_name,
        embedding_dimension=embedding_service.dimension,
        filename=files[0].filename if len(files) == 1 else None,
        chunks=[
            EmbeddingMetadata(chunk_id=embedding.chunk_id, dimension=embedding.dimension)
            for embedding in embeddings
        ],
        errors=errors,
    )