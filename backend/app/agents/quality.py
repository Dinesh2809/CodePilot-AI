from ..services.gemini import GeminiService
from .base import CodeReviewAgent


class CodeQualityAgent(CodeReviewAgent):
    category = "quality"

    def __init__(self, gemini_service: GeminiService) -> None:
        super().__init__(gemini_service)

    @property
    def specialist_instructions(self) -> str:
        return (
            "Look for readability and maintainability problems, duplication, poor "
            "structure, weak error handling, unclear naming, unnecessary complexity, "
            "and other obvious code-quality issues."
        )