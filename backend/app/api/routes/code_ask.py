from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...db.session import get_db_session
from ...schemas.code import CodeAskRequest, CodeAskResponse, CodeUploadError
from ...services.embedding import EmbeddingService
from ...services.gemini import GeminiService
from ...services.rag import RAGService, RAGServiceException
from ...services.semantic_search import SemanticSearchService


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/code", tags=["code"])
search_service = SemanticSearchService(EmbeddingService(settings.EMBEDDING_MODEL))
rag_service = RAGService(
    search_service,
    GeminiService(settings.GEMINI_API_KEY, model_name=settings.GEMINI_MODEL),
)


@router.post("/ask", response_model=CodeAskResponse, response_model_exclude_none=True)
async def ask_code(
    request: CodeAskRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CodeAskResponse:
    try:
        answer, results = await rag_service.ask(
            session, request.query, request.top_k, request.project_id
        )
    except RAGServiceException as error:
        status_code = 422 if error.code in {"EMPTY_TEXT", "INVALID_EMBEDDING_DIMENSION"} else 503
        return JSONResponse(
            status_code=status_code,
            content=CodeAskResponse(
                success=False,
                query=request.query,
                error=CodeUploadError(code=error.code, message=error.message),
            ).model_dump(mode="json", exclude_none=True),
        )
    return CodeAskResponse(
        success=True,
        query=request.query,
        answer=answer,
        retrieved_results=results,
    )