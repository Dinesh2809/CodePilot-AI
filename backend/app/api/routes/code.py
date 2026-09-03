from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from ...core.config import settings
from ...schemas.code import CodeUploadError, CodeUploadResponse
from ...services.code_upload import CodeUploadException, CodeUploadService


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/code", tags=["code"])
upload_service = CodeUploadService(settings.MAX_UPLOAD_SIZE_MB)


@router.post(
    "/upload",
    response_model=CodeUploadResponse,
    response_model_exclude_none=True,
)
async def upload_code(file: UploadFile | None = File(default=None)) -> CodeUploadResponse:
    try:
        metadata = await upload_service.process(file)
    except CodeUploadException as error:
        return JSONResponse(
            status_code=error.status_code,
            content=CodeUploadResponse(
                success=False,
                error=CodeUploadError(code=error.code, message=error.message),
            ).model_dump(exclude_none=True),
        )

    return CodeUploadResponse(success=True, file=metadata)