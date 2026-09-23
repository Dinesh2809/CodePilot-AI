import logging

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...db.session import get_db_session
from ...schemas.code import CodeUploadError, RepositoryIngestionResponse
from ...services.code_upload import CodeUploadService
from ...services.embedding import shared_embedding_service
from ...services.repository_ingestion import (
    RepositoryIngestionException,
    RepositoryIngestionService,
)


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/code", tags=["code"])
logger = logging.getLogger(__name__)
repository_ingestion_service = RepositoryIngestionService(
    upload_service=CodeUploadService(settings.MAX_UPLOAD_SIZE_MB),
    embedding_service=shared_embedding_service,
    max_files_per_batch=settings.MAX_FILES_PER_BATCH,
    max_total_upload_size_mb=settings.MAX_TOTAL_UPLOAD_SIZE_MB,
    embedding_group_size=settings.EMBEDDING_PERSIST_GROUP_SIZE,
)


@router.post(
    "/upload-batch",
    response_model=RepositoryIngestionResponse,
    response_model_exclude_none=True,
)
async def upload_batch(
    files: list[UploadFile] = File(default=[]),
    session: AsyncSession = Depends(get_db_session),
) -> RepositoryIngestionResponse:
    logger.info("upload-batch request received")
    logger.info(
        "upload-batch files received count=%d files=%s",
        len(files),
        [(upload.filename or "[missing]", repository_ingestion_service._upload_size(upload)) for upload in files],
    )
    try:
        response = await repository_ingestion_service.process(files, session)
        logger.info("upload-batch response returning success=%s files=%d chunks=%d", response.success, len(response.files), len(response.chunks))
        return response
    except RepositoryIngestionException as error:
        logger.exception("upload-batch ingestion failed code=%s", error.code)
        return JSONResponse(
            status_code=error.status_code,
            content={
                "success": False,
                "error": CodeUploadError(
                    code=error.code, message=error.message
                ).model_dump(),
            },
        )
    except Exception:
        logger.exception("upload-batch request failed unexpectedly")
        raise