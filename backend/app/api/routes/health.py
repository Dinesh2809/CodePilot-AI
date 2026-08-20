from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return {"status": "healthy"}
