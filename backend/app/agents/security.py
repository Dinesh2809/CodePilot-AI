from ..services.gemini import GeminiService
from .base import CodeReviewAgent


class SecurityAgent(CodeReviewAgent):
    category = "security"

    def __init__(self, gemini_service: GeminiService) -> None:
        super().__init__(gemini_service)

    @property
    def specialist_instructions(self) -> str:
        return (
            "Look for hardcoded secrets, authentication or authorization weaknesses, "
            "unsafe input handling, insecure sensitive-data use, injection risks, "
            "unsafe file or system operations, and other obvious security weaknesses."
        )