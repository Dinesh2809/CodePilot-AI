import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..services.gemini import GeminiService, GeminiServiceException
from .models import AgentAnalysis
from .prompts import build_agent_prompt, parse_agent_response


@dataclass
class AgentException(Exception):
    code: str
    message: str


class CodeReviewAgent(ABC):
    category: str

    def __init__(self, gemini_service: GeminiService) -> None:
        self.gemini_service = gemini_service

    @property
    @abstractmethod
    def specialist_instructions(self) -> str:
        """Return the review focus for this specialist."""

    async def analyze(
        self,
        review_request: str,
        context: list[dict[str, object]],
    ) -> AgentAnalysis:
        prompt = build_agent_prompt(
            review_request,
            context,
            self.specialist_instructions,
        )
        try:
            generation = asyncio.to_thread(self.gemini_service.generate, prompt)
            timeout_seconds = getattr(self.gemini_service, "timeout_seconds", None)
            response_text = (
                await asyncio.wait_for(generation, timeout=timeout_seconds)
                if timeout_seconds is not None
                else await generation
            )
        except GeminiServiceException as error:
            raise AgentException(error.code, error.message) from error
        except TimeoutError as error:
            raise AgentException(
                "GEMINI_TIMEOUT", "The review agent timed out while generating findings."
            ) from error
        except Exception as error:
            raise AgentException(
                "AGENT_EXECUTION_FAILED", "The review agent could not complete analysis."
            ) from error

        try:
            return parse_agent_response(response_text)
        except ValueError as error:
            raise AgentException(
                "MALFORMED_AGENT_RESPONSE",
                "The review agent returned invalid structured findings.",
            ) from error