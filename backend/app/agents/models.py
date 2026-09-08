from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReviewCategory = Literal["security", "quality", "performance"]
ReviewSeverity = Literal["critical", "high", "medium", "low", "info"]
ReviewAgent = Literal["security", "quality", "performance"]


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ReviewCategory
    severity: ReviewSeverity
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    recommendation: str = Field(min_length=1)


class AgentAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ReviewFinding] = Field(default_factory=list)


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: ReviewAgent
    success: bool
    findings: list[ReviewFinding] = Field(default_factory=list)
    error: str | None = None


class FinalReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    findings: list[ReviewFinding] = Field(default_factory=list)
    total_findings: int = Field(ge=0)
    critical_count: int = Field(ge=0)
    high_count: int = Field(ge=0)
    medium_count: int = Field(ge=0)
    low_count: int = Field(ge=0)
    info_count: int = Field(ge=0)
    categories: list[ReviewCategory] = Field(default_factory=list)
    agents_completed: list[ReviewAgent] = Field(default_factory=list)
    agents_failed: list[ReviewAgent] = Field(default_factory=list)