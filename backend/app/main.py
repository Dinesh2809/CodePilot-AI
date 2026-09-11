from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .api.routes.health import router as health_router
from .api.routes.code import router as code_router
from .api.routes.code_parse import router as code_parse_router
from .api.routes.code_chunk import router as code_chunk_router
from .api.routes.code_batch import router as code_batch_router
from .api.routes.code_embed import router as code_embed_router
from .api.routes.code_search import router as code_search_router
from .api.routes.code_ask import router as code_ask_router
from .api.routes.code_review import router as code_review_router


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for the CodePilot AI developer assistant.",
    debug=settings.DEBUG and settings.APP_ENV.lower() not in {"prod", "production"},
)

if "*" in settings.CORS_ORIGINS:
    raise ValueError("CORS_ORIGINS must not contain a wildcard origin.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith(settings.API_V1_PREFIX) or request.url.path in {
        "/health",
        "/ready",
    }:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_error(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request contains invalid or missing values.",
            },
        },
    )


# Register routers
app.include_router(health_router)
app.include_router(code_router)
app.include_router(code_parse_router)
app.include_router(code_chunk_router)
app.include_router(code_batch_router)
app.include_router(code_embed_router)
app.include_router(code_search_router)
app.include_router(code_ask_router)
app.include_router(code_review_router)
