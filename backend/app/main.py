from fastapi import FastAPI

from backend.app.core.config import settings
from backend.app.api.routes.health import router as health_router


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for the CodePilot AI developer assistant.",
    debug=settings.DEBUG,
)


# Register routers
app.include_router(health_router)
