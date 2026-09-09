from collections.abc import Iterable, Mapping

from .models import (
    AgentAnalysis,
    AgentRunResult,
    FinalReview,
    ReviewAgent,
    ReviewFinding,
    ReviewSeverity,
)


AGENT_ORDER: tuple[ReviewAgent, ...] = ("security", "quality", "performance")
SEVERITY_ORDER: dict[ReviewSeverity, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


class ReviewAggregator:
    """Combine specialist findings without another model call."""

    def aggregate(
        self,
        agent_results: Mapping[str, AgentRunResult | AgentAnalysis | None],
    ) -> FinalReview:
        normalized = self._normalize_results(agent_results)
        findings = self._deduplicate(
            finding
            for result in normalized.values()
            if result.success
            for finding in result.findings
            if self._is_valid_agent_finding(result.agent, finding)
        )
        findings.sort(key=self._finding_sort_key)

        completed = [agent for agent in AGENT_ORDER if normalized[agent].success]
        failed = [agent for agent in AGENT_ORDER if not normalized[agent].success]
        counts = {severity: 0 for severity in SEVERITY_ORDER}
        for finding in findings:
            counts[finding.severity] += 1

        categories = [
            category
            for category in ("security", "quality", "performance")
            if any(finding.category == category for finding in findings)
        ]
        return FinalReview(
            summary=self._summary(findings, completed, failed),
            findings=findings,
            total_findings=len(findings),
            critical_count=counts["critical"],
            high_count=counts["high"],
            medium_count=counts["medium"],
            low_count=counts["low"],
            info_count=counts["info"],
            categories=categories,
            agents_completed=completed,
            agents_failed=failed,
        )

    @staticmethod
    def _normalize_results(
        agent_results: Mapping[str, AgentRunResult | AgentAnalysis | None],
    ) -> dict[ReviewAgent, AgentRunResult]:
        normalized: dict[ReviewAgent, AgentRunResult] = {}
        for agent in AGENT_ORDER:
            result = agent_results.get(agent)
            if isinstance(result, AgentRunResult):
                normalized[agent] = result.model_copy(update={"agent": agent})
            elif isinstance(result, AgentAnalysis):
                normalized[agent] = AgentRunResult(
                    agent=agent,
                    success=True,
                    findings=result.findings,
                )
            else:
                normalized[agent] = AgentRunResult(
                    agent=agent,
                    success=False,
                    error="Agent result was unavailable.",
                )
        return normalized

    @staticmethod
    def _is_valid_agent_finding(agent: ReviewAgent, finding: ReviewFinding) -> bool:
        """Validate that a finding's category matches the agent type."""
        return finding.category == agent

    @staticmethod
    def _deduplicate(findings: Iterable[ReviewFinding]) -> list[ReviewFinding]:
        unique: dict[tuple[object, ...], ReviewFinding] = {}
        for finding in findings:
            key = (
                finding.category,
                finding.filename,
                finding.start_line,
                finding.end_line,
            )
            existing = unique.get(key)
            if existing is None or (
                ReviewAggregator._finding_tie_key(finding)
                < ReviewAggregator._finding_tie_key(existing)
            ):
                unique[key] = finding
        return list(unique.values())

    @staticmethod
    def _finding_tie_key(finding: ReviewFinding) -> tuple[object, ...]:
        return (
            SEVERITY_ORDER[finding.severity],
            finding.description,
            finding.recommendation,
        )

    @staticmethod
    def _finding_sort_key(finding: ReviewFinding) -> tuple[object, ...]:
        return (
            SEVERITY_ORDER[finding.severity],
            finding.category,
            finding.filename,
            finding.start_line,
            finding.end_line,
            finding.title,
            finding.description,
            finding.recommendation,
        )

    @staticmethod
    def _summary(
        findings: list[ReviewFinding],
        completed: list[ReviewAgent],
        failed: list[ReviewAgent],
    ) -> str:
        if not findings:
            summary = "No issues were identified in the supplied context."
        else:
            categories = ", ".join(
                category
                for category in ("security", "quality", "performance")
                if any(finding.category == category for finding in findings)
            )
            highest = findings[0].severity
            summary = (
                f"Found {len(findings)} issue{'s' if len(findings) != 1 else ''} "
                f"across {categories}. Highest severity: {highest}."
            )
        if failed:
            summary += f" Agents failed: {', '.join(failed)}."
        return summary