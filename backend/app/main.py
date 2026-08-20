from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"


app = FastAPI(
    title="CodePilot AI",
    description="Backend API for the CodePilot AI developer assistant.",
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return {"status": "healthy"}
