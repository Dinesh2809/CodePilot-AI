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
    try:
        return await repository_ingestion_service.process(files, session)
    except RepositoryIngestionException as error:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "success": False,
                "error": CodeUploadError(
                    code=error.code, message=error.message
                ).model_dump(),
            },
        )