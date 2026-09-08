from ..services.gemini import GeminiService
from .base import CodeReviewAgent


class PerformanceAgent(CodeReviewAgent):
    category = "performance"

    def __init__(self, gemini_service: GeminiService) -> None:
        super().__init__(gemini_service)

    @property
    def specialist_instructions(self) -> str:
        return (
            "Look for inefficient loops, repeated expensive operations, unnecessary "
            "computation or memory use, inefficient database or API usage, and obvious "
            "scalability concerns supported by the supplied code."
        )