from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...db.session import get_db_session
from ...schemas.code import CodeReviewRequest, CodeReviewResponse, CodeUploadError
from ...services.embedding import EmbeddingService
from ...services.gemini import GeminiService, GeminiServiceException
from ...services.review_orchestrator import ReviewOrchestrator
from ...services.semantic_search import SemanticSearchException, SemanticSearchService


router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/code", tags=["code"])
search_service = SemanticSearchService(EmbeddingService(settings.EMBEDDING_MODEL))
gemini_service = GeminiService(settings.GEMINI_API_KEY, model_name=settings.GEMINI_MODEL)
orchestrator = ReviewOrchestrator(gemini_service)


@router.post(
    "/review",
    response_model=CodeReviewResponse,
    response_model_exclude_none=True,
)
async def review_code(
    request: CodeReviewRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CodeReviewResponse:
    """
    Perform a comprehensive code review using specialized agents.

    Runs concurrent security, quality, and performance reviews on retrieved code context.
    """
    try:
        # Retrieve relevant code chunks using existing semantic search
        results = await search_service.search(
            session, request.query, top_k=request.top_k, project_id=request.project_id
        )
    except SemanticSearchException as error:
        status_code = 422 if error.code in {"EMPTY_TEXT", "INVALID_EMBEDDING_DIMENSION"} else 503
        return JSONResponse(
            status_code=status_code,
            content=CodeReviewResponse(
                success=False,
                query=request.query,
                error=CodeUploadError(code=error.code, message=error.message),
            ).model_dump(mode="json", exclude_none=True),
        )

    if not results:
        # Handle empty retrieval gracefully
        return CodeReviewResponse(
            success=True,
            query=request.query,
            summary="No relevant code context was found to review.",
            findings=[],
            total_findings=0,
            categories=[],
            agents_completed=[],
            agents_failed=[],
        )

    try:
        # Run orchestrator with retrieved context
        final_review = await orchestrator.review(request.query, results)
    except GeminiServiceException as error:
        status_code = 503
        return JSONResponse(
            status_code=status_code,
            content=CodeReviewResponse(
                success=False,
                query=request.query,
                error=CodeUploadError(code=error.code, message=error.message),
            ).model_dump(mode="json", exclude_none=True),
        )
    except Exception as error:
        return JSONResponse(
            status_code=500,
            content=CodeReviewResponse(
                success=False,
                query=request.query,
                error=CodeUploadError(
                    code="REVIEW_FAILED",
                    message="An unexpected error occurred during review.",
                ),
            ).model_dump(mode="json", exclude_none=True),
        )

    # Convert findings to dict format for response
    findings_dicts = [finding.model_dump() for finding in final_review.findings]

    return CodeReviewResponse(
        success=True,
        query=request.query,
        summary=final_review.summary,
        findings=findings_dicts,
        total_findings=final_review.total_findings,
        critical_count=final_review.critical_count,
        high_count=final_review.high_count,
        medium_count=final_review.medium_count,
        low_count=final_review.low_count,
        info_count=final_review.info_count,
        categories=final_review.categories,
        agents_completed=final_review.agents_completed,
        agents_failed=final_review.agents_failed,
    )
