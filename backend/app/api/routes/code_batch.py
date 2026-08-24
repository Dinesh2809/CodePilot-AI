from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.schemas.code import CodeUploadError, RepositoryIngestionResponse
from backend.app.services.code_upload import CodeUploadService
from backend.app.services.repository_ingestion import (
    RepositoryIngestionException,
    RepositoryIngestionService,
)


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/code", tags=["code"])
repository_ingestion_service = RepositoryIngestionService(
    upload_service=CodeUploadService(settings.MAX_UPLOAD_SIZE_MB),
    max_files_per_batch=settings.MAX_FILES_PER_BATCH,
)


@router.post(
    "/upload-batch",
    response_model=RepositoryIngestionResponse,
    response_model_exclude_none=True,
)
async def upload_batch(
    files: list[UploadFile] = File(default=[]),
) -> RepositoryIngestionResponse:
    try:
        return await repository_ingestion_service.process(files)
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