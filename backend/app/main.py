from fastapi import FastAPI

from .core.config import settings
from .api.routes.health import router as health_router
from .api.routes.code import router as code_router
from .api.routes.code_parse import router as code_parse_router
from .api.routes.code_chunk import router as code_chunk_router
from .api.routes.code_batch import router as code_batch_router
from .api.routes.code_embed import router as code_embed_router
from .api.routes.code_search import router as code_search_router


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for the CodePilot AI developer assistant.",
    debug=settings.DEBUG,
)


# Register routers
app.include_router(health_router)
app.include_router(code_router)
app.include_router(code_parse_router)
app.include_router(code_chunk_router)
app.include_router(code_batch_router)
app.include_router(code_embed_router)
app.include_router(code_search_router)
