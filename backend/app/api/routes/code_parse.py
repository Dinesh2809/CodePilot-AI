from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.schemas.code import CodeParseResult, CodeUploadError
from backend.app.services.code_parser import PythonCodeParser
from backend.app.services.code_upload import (
    CodeUploadException,
    CodeUploadService,
)


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/code", tags=["code"])
upload_service = CodeUploadService(settings.MAX_UPLOAD_SIZE_MB)
python_parser = PythonCodeParser()


@router.post(
    "/parse",
    response_model=CodeParseResult,
    response_model_exclude_none=True,
)
async def parse_code(file: UploadFile | None = File(default=None)) -> CodeParseResult:
    try:
        metadata, source = await upload_service.read_source(file)
    except CodeUploadException as error:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "success": False,
                "error": CodeUploadError(code=error.code, message=error.message).model_dump(),
            },
        )

    if metadata.extension != ".py":
        return JSONResponse(
            status_code=501,
            content={
                "success": False,
                "error": CodeUploadError(
                    code="PARSER_NOT_IMPLEMENTED",
                    message="Parsing is currently supported only for Python files.",
                ).model_dump(),
            },
        )

    try:
        return python_parser.parse(source, metadata.filename, metadata.line_count)
    except ValueError as error:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": CodeUploadError(code="SYNTAX_ERROR", message=str(error)).model_dump(),
            },
        )