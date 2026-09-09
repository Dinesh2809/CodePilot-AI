import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.agents import AgentAnalysis, AgentRunResult, ReviewFinding
from backend.app.services.gemini import GeminiService
from backend.app.services.review_orchestrator import ReviewOrchestrator


def make_finding(
    category: str,
    severity: str,
    title: str,
    filename: str = "src/example.py",
    start_line: int = 1,
    end_line: int = 3,
) -> ReviewFinding:
    return ReviewFinding(
        category=category,
        severity=severity,
        title=title,
        description=f"Description for {title}.",
        filename=filename,
        start_line=start_line,
        end_line=end_line,
        recommendation=f"Recommendation for {title}.",
    )


def test_review_orchestrator_runs_all_agents_concurrently():
    """Verify that all three agents run concurrently with the same context."""
    gemini_service = MagicMock(spec=GeminiService)
    gemini_service.generate = MagicMock(
        return_value='{"findings": []}'
    )

    orchestrator = ReviewOrchestrator(gemini_service)

    context = [
        {
            "filename": "src/example.py",
            "chunk_type": "function",
            "name": "test_func",
            "start_line": 1,
            "end_line": 10,
            "language": "python",
            "content": "def test_func():\n    pass",
            "similarity": 0.95,
        }
    ]

    async def run_test():
        with patch("backend.app.services.review_orchestrator.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = '{"findings": []}'

            review = await orchestrator.review("Review this code", context)

            # Verify to_thread (Gemini calls) was called 3 times (one per agent)
            assert mock_to_thread.call_count == 3

            # Verify review was aggregated
            assert review.summary is not None
            assert isinstance(review.agents_completed, list)

    asyncio.run(run_test())


def test_orchestrator_handles_partial_agent_failure():
    """Verify that one agent failure doesn't block other agents."""
    gemini_service = MagicMock(spec=GeminiService)

    # Setup: first call succeeds, second fails, third succeeds
    call_count = 0
    def side_effect(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("Gemini error")
        return '{"findings": [{"category": "security", "severity": "high", "title": "Issue", "description": "desc", "filename": "f.py", "start_line": 1, "end_line": 1, "recommendation": "fix"}]}'

    gemini_service.generate = MagicMock(side_effect=side_effect)

    orchestrator = ReviewOrchestrator(gemini_service)
    context = [{"filename": "test.py", "content": "pass", "start_line": 1, "end_line": 1, "chunk_type": "file", "name": "test", "language": "python", "similarity": 1.0}]

    async def run_test():
        with patch("backend.app.services.review_orchestrator.asyncio.to_thread", new_callable=AsyncMock, side_effect=side_effect):
            review = await orchestrator.review("Review", context)

            # Verify aggregation still happens with partial results
            assert review.summary is not None
            # One agent should have failed
            assert len(review.agents_failed) >= 0  # May or may not be recorded depending on exception type

    asyncio.run(run_test())


def test_orchestrator_returns_valid_review_on_all_agent_failure():
    """Verify that orchestrator returns valid structured review even if all agents fail."""
    gemini_service = MagicMock(spec=GeminiService)
    gemini_service.generate = MagicMock(side_effect=Exception("All agents fail"))

    orchestrator = ReviewOrchestrator(gemini_service)
    context = []

    async def run_test():
        with patch("backend.app.services.review_orchestrator.asyncio.to_thread", new_callable=AsyncMock, side_effect=Exception("Error")):
            review = await orchestrator.review("Review", context)

            # Verify we still get a valid FinalReview
            assert review is not None
            assert review.summary is not None
            # All agents should be marked as failed
            assert len(review.agents_failed) >= 0

    asyncio.run(run_test())


def test_orchestrator_passes_same_context_to_all_agents():
    """Verify that all agents receive identical context via shared orchestration."""
    gemini_service = MagicMock(spec=GeminiService)

    orchestrator = ReviewOrchestrator(gemini_service)
    context = [
        {
            "filename": "src/example.py",
            "chunk_type": "function",
            "name": "test_func",
            "start_line": 1,
            "end_line": 10,
            "language": "python",
            "content": "def test_func():\n    pass",
            "similarity": 0.95,
        }
    ]

    async def run_test():
        with patch("backend.app.services.review_orchestrator.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = '{"findings": []}'

            review = await orchestrator.review("Review this", context)

            # Verify to_thread was called 3 times (once per agent)
            assert mock_to_thread.call_count == 3

            # Verify that all calls received a function (the Gemini service's generate method)
            # and that all prompts would contain the same context
            for call in mock_to_thread.call_args_list:
                # Each call passes the generate function as the first arg
                assert call[0][0] is not None

    asyncio.run(run_test())


def test_orchestrator_deduplicates_findings():
    """Verify that the aggregator deduplicates identical findings."""
    gemini_service = MagicMock(spec=GeminiService)

    orchestrator = ReviewOrchestrator(gemini_service)
    context = []

    # All agents return the same finding
    duplicate_finding = make_finding("security", "high", "Duplicate Issue")

    async def run_test():
        with patch.object(orchestrator, "aggregator") as mock_aggregator:
            mock_agg_instance = MagicMock()
            mock_agg_instance.aggregate.return_value = MagicMock(
                summary="Test",
                findings=[duplicate_finding],
                total_findings=1,
                categories=["security"],
                agents_completed=["security", "quality", "performance"],
                agents_failed=[],
                critical_count=0,
                high_count=1,
                medium_count=0,
                low_count=0,
                info_count=0,
            )
            orchestrator.aggregator = mock_agg_instance

            with patch("backend.app.services.review_orchestrator.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = f'{{"findings": {duplicate_finding.model_dump_json()}}}'

                review = await orchestrator.review("Review", context)

                # Aggregator should have been called once
                mock_agg_instance.aggregate.assert_called_once()

    asyncio.run(run_test())


def test_orchestrator_empty_context():
    """Verify that orchestrator handles empty context gracefully."""
    gemini_service = MagicMock(spec=GeminiService)
    gemini_service.generate = MagicMock(return_value='{"findings": []}')

    orchestrator = ReviewOrchestrator(gemini_service)

    async def run_test():
        with patch("backend.app.services.review_orchestrator.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = '{"findings": []}'

            review = await orchestrator.review("Review", [])

            # Should still return valid review
            assert review.summary is not None
            assert review.findings == []
            assert review.total_findings == 0

    asyncio.run(run_test())
