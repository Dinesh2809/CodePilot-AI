from backend.app.agents import (
    AgentAnalysis,
    AgentRunResult,
    FinalReview,
    ReviewAggregator,
    ReviewFinding,
)


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


def successful(*findings: ReviewFinding) -> AgentRunResult:
    return AgentRunResult(agent="security", success=True, findings=list(findings))


def test_aggregates_all_specialist_findings() -> None:
    review = ReviewAggregator().aggregate(
        {
            "security": AgentAnalysis(findings=[make_finding("security", "high", "Secret")]),
            "quality": AgentAnalysis(findings=[make_finding("quality", "medium", "Naming")]),
            "performance": AgentAnalysis(findings=[make_finding("performance", "low", "Loop")]),
        }
    )

    assert isinstance(review, FinalReview)
    assert review.total_findings == 3
    assert review.categories == ["security", "quality", "performance"]
    assert review.agents_completed == ["security", "quality", "performance"]
    assert review.agents_failed == []


def test_deduplicates_only_matching_stable_fields() -> None:
    duplicate = make_finding("security", "medium", "Secret")
    duplicate_with_better_severity = make_finding("security", "high", "Secret")
    similar_title = make_finding("security", "high", "Different title")

    review = ReviewAggregator().aggregate(
        {
            "security": successful(duplicate),
            "quality": successful(duplicate_with_better_severity, similar_title),
        }
    )

    assert review.total_findings == 2
    assert {finding.title for finding in review.findings} == {
        "Secret",
        "Different title",
    }
    assert next(finding for finding in review.findings if finding.title == "Secret").severity == "high"


def test_sorts_by_severity_and_counts_findings() -> None:
    review = ReviewAggregator().aggregate(
        {
            "security": successful(
                make_finding("security", "low", "Low"),
                make_finding("security", "critical", "Critical"),
            ),
            "quality": successful(make_finding("quality", "high", "High")),
            "performance": successful(
                make_finding("performance", "medium", "Medium"),
                make_finding("performance", "info", "Info"),
            ),
        }
    )

    assert [finding.severity for finding in review.findings] == [
        "critical",
        "high",
        "medium",
        "low",
        "info",
    ]
    assert review.critical_count == 1
    assert review.high_count == 1
    assert review.medium_count == 1
    assert review.low_count == 1
    assert review.info_count == 1


def test_partial_agent_failure_preserves_successful_findings() -> None:
    review = ReviewAggregator().aggregate(
        {
            "security": successful(make_finding("security", "high", "Auth")),
            "quality": AgentRunResult(
                agent="quality",
                success=False,
                error="MALFORMED_AGENT_RESPONSE",
            ),
        }
    )

    assert review.total_findings == 1
    assert review.agents_completed == ["security"]
    assert review.agents_failed == ["quality", "performance"]
    assert "Agents failed: quality, performance." in review.summary


def test_all_agents_without_findings_returns_valid_empty_review() -> None:
    review = ReviewAggregator().aggregate(
        {
            "security": AgentAnalysis(),
            "quality": AgentAnalysis(),
            "performance": AgentAnalysis(),
        }
    )

    assert review.total_findings == 0
    assert review.findings == []
    assert review.categories == []
    assert review.critical_count == 0
    assert review.summary == "No issues were identified in the supplied context."


def test_empty_input_is_safe_and_deterministic() -> None:
    first = ReviewAggregator().aggregate({})
    second = ReviewAggregator().aggregate({})

    assert first == second
    assert first.total_findings == 0
    assert first.agents_completed == []
    assert first.agents_failed == ["security", "quality", "performance"]


def test_same_findings_have_stable_order_independent_of_input_order() -> None:
    findings = [
        make_finding("quality", "medium", "B", filename="b.py"),
        make_finding("security", "medium", "A", filename="a.py"),
    ]
    first = ReviewAggregator().aggregate(
        {"security": successful(findings[0]), "quality": successful(findings[1])}
    )
    second = ReviewAggregator().aggregate(
        {"quality": successful(findings[1]), "security": successful(findings[0])}
    )

    assert first.findings == second.findings
    assert first.summary == second.summary