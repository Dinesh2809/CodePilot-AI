from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import engine, get_db


router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    await db.execute(text("SELECT 1"))
    return {"status": "healthy"}


@router.get("/ready", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse | JSONResponse:
    if engine is None:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Required infrastructure is unavailable.",
                },
            },
        )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Required infrastructure is unavailable.",
                },
            },
        )
    return ReadinessResponse()
