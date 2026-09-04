from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...db.session import get_db_session
from ...schemas.code import (
    CodeSearchRequest,
    CodeSearchResponse,
    CodeUploadError,
)
from ...services.embedding import EmbeddingService
from ...services.semantic_search import SemanticSearchException, SemanticSearchService


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/code", tags=["code"])
embedding_service = EmbeddingService(settings.EMBEDDING_MODEL)
semantic_search_service = SemanticSearchService(embedding_service)


@router.post("/search", response_model=CodeSearchResponse, response_model_exclude_none=True)
async def search_code(
    request: CodeSearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CodeSearchResponse:
    try:
        results = await semantic_search_service.search(
            session=session,
            query=request.query,
            top_k=request.top_k,
            project_id=request.project_id,
        )
    except SemanticSearchException as error:
        status_code = 422 if error.code in {"EMPTY_TEXT", "INVALID_EMBEDDING_DIMENSION"} else 503
        return JSONResponse(
            status_code=status_code,
            content=CodeSearchResponse(
                success=False,
                query=request.query,
                error=CodeUploadError(code=error.code, message=error.message),
            ).model_dump(mode="json", exclude_none=True),
        )

    return CodeSearchResponse(
        success=True,
        query=request.query,
        results=results,
        result_count=len(results),
    )