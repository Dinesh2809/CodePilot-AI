import asyncio
from typing import Any

from ..agents.aggregator import ReviewAggregator
from ..agents.base import AgentException
from ..agents.models import AgentRunResult, FinalReview
from ..agents.performance import PerformanceAgent
from ..agents.quality import CodeQualityAgent
from ..agents.security import SecurityAgent
from .gemini import GeminiService, GeminiServiceException


class ReviewOrchestrator:
    """Orchestrate concurrent code review by specialist agents."""

    def __init__(self, gemini_service: GeminiService) -> None:
        self.gemini_service = gemini_service
        self.aggregator = ReviewAggregator()

    async def review(
        self,
        review_request: str,
        context: list[dict[str, Any]],
    ) -> FinalReview:
        """
        Execute concurrent review by all specialist agents.

        All three agents receive the same retrieved context.
        Individual agent failures do not block the orchestration.
        A final structured review is always returned.
        """
        if not context:
            # Empty context produces valid but finding-less review
            context = []

        # Create agent instances (they share the same GeminiService)
        security_agent = SecurityAgent(self.gemini_service)
        quality_agent = CodeQualityAgent(self.gemini_service)
        performance_agent = PerformanceAgent(self.gemini_service)

        # Run all agents concurrently with individual exception handling
        results = await asyncio.gather(
            self._run_agent(security_agent, review_request, context),
            self._run_agent(quality_agent, review_request, context),
            self._run_agent(performance_agent, review_request, context),
            return_exceptions=False,
        )

        # Map results to agent names
        agent_results = {
            "security": results[0],
            "quality": results[1],
            "performance": results[2],
        }

        # Aggregate findings from all agents
        return self.aggregator.aggregate(agent_results)

    @staticmethod
    async def _run_agent(
        agent: Any,
        review_request: str,
        context: list[dict[str, Any]],
    ) -> AgentRunResult:
        """Run a single agent with exception handling."""
        try:
            analysis = await agent.analyze(review_request, context)
            return AgentRunResult(
                agent=agent.category,
                success=True,
                findings=analysis.findings,
            )
        except AgentException as error:
            return AgentRunResult(
                agent=agent.category,
                success=False,
                findings=[],
                error=error.message,
            )
        except GeminiServiceException as error:
            return AgentRunResult(
                agent=agent.category,
                success=False,
                findings=[],
                error=error.message,
            )
        except Exception as error:
            return AgentRunResult(
                agent=agent.category,
                success=False,
                findings=[],
                error="An unexpected error occurred during review.",
            )
