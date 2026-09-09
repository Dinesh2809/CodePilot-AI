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
    return AgentRunResult(
        agent=findings[0].category,
        success=True,
        findings=list(findings),
    )


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


def test_deduplicates_same_location_even_with_different_titles() -> None:
    duplicate = make_finding("security", "medium", "Secret")
    duplicate_with_better_severity = make_finding("security", "high", "Secret")
    similar_title = make_finding("security", "high", "Different title")

    review = ReviewAggregator().aggregate(
        {
            "security": successful(
                duplicate,
                duplicate_with_better_severity,
                similar_title,
            ),
        }
    )

    assert review.total_findings == 1
    assert review.findings[0].severity == "high"


def test_sorts_by_severity_and_counts_findings() -> None:
    review = ReviewAggregator().aggregate(
        {
            "security": successful(
                make_finding("security", "low", "Low", start_line=1, end_line=2),
                make_finding("security", "critical", "Critical", start_line=3, end_line=4),
            ),
            "quality": successful(
                make_finding("quality", "high", "High", start_line=5, end_line=6)
            ),
            "performance": successful(
                make_finding("performance", "medium", "Medium", start_line=7, end_line=8),
                make_finding("performance", "info", "Info", start_line=9, end_line=10),
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
        {"security": successful(findings[1]), "quality": successful(findings[0])}
    )
    second = ReviewAggregator().aggregate(
        {"quality": successful(findings[0]), "security": successful(findings[1])}
    )

    assert first.findings == second.findings
    assert first.summary == second.summary


def test_cross_category_filtering_security_agent_quality_finding() -> None:
    """SecurityAgent returning a quality finding should be filtered out."""
    aggregator = ReviewAggregator()
    quality_finding = make_finding("quality", "medium", "Poor naming", filename="src/auth.py", start_line=1, end_line=5)

    review = aggregator.aggregate(
        {
            "security": AgentRunResult(
                agent="security",
                success=True,
                findings=[quality_finding],  # SecurityAgent returning quality finding
            ),
            "quality": AgentRunResult(agent="quality", success=True, findings=[]),
            "performance": AgentRunResult(agent="performance", success=True, findings=[]),
        }
    )

    # Quality finding from security agent should be discarded
    assert review.total_findings == 0
    assert "quality" not in [f.category for f in review.findings]


def test_cross_category_filtering_quality_agent_security_finding() -> None:
    """QualityAgent returning a security finding should be filtered out."""
    aggregator = ReviewAggregator()
    security_finding = make_finding("security", "critical", "SQL Injection", filename="src/auth.py", start_line=1, end_line=5)

    review = aggregator.aggregate(
        {
            "security": AgentRunResult(agent="security", success=True, findings=[]),
            "quality": AgentRunResult(
                agent="quality",
                success=True,
                findings=[security_finding],  # QualityAgent returning security finding
            ),
            "performance": AgentRunResult(agent="performance", success=True, findings=[]),
        }
    )

    # Security finding from quality agent should be discarded
    assert review.total_findings == 0
    assert "security" not in [f.category for f in review.findings]


def test_cross_category_filtering_performance_agent_security_finding() -> None:
    """PerformanceAgent returning a security finding should be filtered out."""
    aggregator = ReviewAggregator()
    security_finding = make_finding("security", "high", "Hardcoded Secret", filename="src/auth.py", start_line=10, end_line=15)

    review = aggregator.aggregate(
        {
            "security": AgentRunResult(agent="security", success=True, findings=[]),
            "quality": AgentRunResult(agent="quality", success=True, findings=[]),
            "performance": AgentRunResult(
                agent="performance",
                success=True,
                findings=[security_finding],  # PerformanceAgent returning security finding
            ),
        }
    )

    # Security finding from performance agent should be discarded
    assert review.total_findings == 0
    assert "security" not in [f.category for f in review.findings]


def test_deduplicates_same_location_different_titles() -> None:
    """Same location with different titles should deduplicate to one finding."""
    aggregator = ReviewAggregator()

    finding1 = make_finding(
        "security",
        "high",
        "Hardcoded Authentication Bypass",
        filename="src/auth.py",
        start_line=1,
        end_line=2,
    )
    finding2 = ReviewFinding(
        category="security",
        severity="high",
        title="Hardcoded Authentication Bypass in login function",
        description="Authentication is hardcoded in the login function",
        filename="src/auth.py",
        start_line=1,
        end_line=2,
        recommendation="Use dynamic authentication",
    )

    review = aggregator.aggregate(
        {
            "security": AgentRunResult(
                agent="security",
                success=True,
                findings=[finding1, finding2],
            ),
            "quality": AgentRunResult(agent="quality", success=True, findings=[]),
            "performance": AgentRunResult(agent="performance", success=True, findings=[]),
        }
    )

    # Should deduplicate to exactly one finding due to same location
    assert review.total_findings == 1
    assert review.findings[0].filename == "src/auth.py"
    assert review.findings[0].start_line == 1
    assert review.findings[0].end_line == 2


def test_deduplicates_preserves_better_severity_on_tie() -> None:
    """When deduplicating same location, preserve the finding with better (lower) severity ordering."""
    aggregator = ReviewAggregator()

    finding_low = make_finding(
        "quality",
        "low",
        "Minor issue",
        filename="src/code.py",
        start_line=10,
        end_line=15,
    )
    finding_medium = ReviewFinding(
        category="quality",
        severity="medium",
        title="Same location issue",
        description="Different description same location",
        filename="src/code.py",
        start_line=10,
        end_line=15,
        recommendation="Fix this",
    )

    review = aggregator.aggregate(
        {
            "security": AgentRunResult(agent="security", success=True, findings=[]),
            "quality": AgentRunResult(
                agent="quality",
                success=True,
                findings=[finding_medium, finding_low],  # low severity should be kept
            ),
            "performance": AgentRunResult(agent="performance", success=True, findings=[]),
        }
    )

    assert review.total_findings == 1
    # Lower severity value (more severe) should be preserved: critical < high < medium < low < info
    # In this case, low (3) vs medium (2), medium is more severe so it's kept
    assert review.findings[0].severity == "medium"


def test_different_locations_not_deduplicated() -> None:
    """Same title but different locations should NOT be deduplicated."""
    aggregator = ReviewAggregator()

    finding1 = make_finding(
        "security",
        "high",
        "Hardcoded Secret",
        filename="src/auth.py",
        start_line=1,
        end_line=5,
    )
    finding2 = make_finding(
        "security",
        "high",
        "Hardcoded Secret",
        filename="src/auth.py",
        start_line=10,
        end_line=15,
    )

    review = aggregator.aggregate(
        {
            "security": AgentRunResult(
                agent="security",
                success=True,
                findings=[finding1, finding2],
            ),
            "quality": AgentRunResult(agent="quality", success=True, findings=[]),
            "performance": AgentRunResult(agent="performance", success=True, findings=[]),
        }
    )

    # Both findings should be preserved (different line ranges)
    assert review.total_findings == 2


def test_different_files_not_deduplicated() -> None:
    """Same title but different files should NOT be deduplicated."""
    aggregator = ReviewAggregator()

    finding1 = make_finding(
        "quality",
        "medium",
        "Poor naming",
        filename="src/auth.py",
        start_line=1,
        end_line=5,
    )
    finding2 = make_finding(
        "quality",
        "medium",
        "Poor naming",
        filename="src/config.py",
        start_line=1,
        end_line=5,
    )

    review = aggregator.aggregate(
        {
            "security": AgentRunResult(agent="security", success=True, findings=[]),
            "quality": AgentRunResult(
                agent="quality",
                success=True,
                findings=[finding1, finding2],
            ),
            "performance": AgentRunResult(agent="performance", success=True, findings=[]),
        }
    )

    # Both findings should be preserved (different files)
    assert review.total_findings == 2


def test_failed_agent_has_explicit_empty_findings() -> None:
    """Failed agents must have findings=[] and success=False."""
    aggregator = ReviewAggregator()

    failed_result = AgentRunResult(
        agent="security",
        success=False,
        findings=[],  # Explicitly empty
        error="Gemini error",
    )

    review = aggregator.aggregate(
        {
            "security": failed_result,
            "quality": AgentRunResult(agent="quality", success=True, findings=[]),
            "performance": AgentRunResult(agent="performance", success=True, findings=[]),
        }
    )

    assert "security" in review.agents_failed
    assert "security" not in review.agents_completed
    assert review.total_findings == 0


def test_failed_agent_findings_not_included() -> None:
    """Even if a failed agent somehow has findings, they should not be included."""
    aggregator = ReviewAggregator()

    # This scenario should not happen (exception handling ensures findings=[]),
    # but we test the guard for robustness
    failed_result = AgentRunResult(
        agent="security",
        success=False,
        findings=[make_finding("security", "critical", "Test")],  # Should never happen
        error="Error",
    )

    review = aggregator.aggregate(
        {
            "security": failed_result,
            "quality": AgentRunResult(agent="quality", success=True, findings=[]),
            "performance": AgentRunResult(agent="performance", success=True, findings=[]),
        }
    )

    # Failed agent findings should not appear
    assert review.total_findings == 0
    assert review.agents_failed == ["security"]