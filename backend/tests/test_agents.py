import asyncio
import json
import threading

import pytest
from pydantic import ValidationError

from backend.app.agents import (
    AgentAnalysis,
    AgentException,
    CodeQualityAgent,
    PerformanceAgent,
    ReviewFinding,
    SecurityAgent,
)
from backend.app.services.gemini import GeminiServiceException


CONTEXT = [
    {
        "filename": "src/auth.py",
        "chunk_type": "function",
        "name": "login",
        "start_line": 4,
        "end_line": 8,
        "language": "python",
        "content": "def login(user):\n    return authenticate(user)",
        "similarity": 0.88,
    }
]


def finding_payload(category: str = "security") -> dict[str, object]:
    return {
        "category": category,
        "severity": "high",
        "title": "Authentication result is not checked",
        "description": "The supplied function does not show an authentication check.",
        "filename": "src/auth.py",
        "start_line": 4,
        "end_line": 8,
        "recommendation": "Validate the authentication result before continuing.",
    }


class FakeGemini:
    def __init__(self, response: str = "{\"findings\": []}") -> None:
        self.response = response
        self.prompts: list[str] = []
        self.thread_ids: list[int] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        self.thread_ids.append(threading.get_ident())
        return self.response


class FailingGemini:
    def generate(self, prompt: str) -> str:
        raise GeminiServiceException("GEMINI_REQUEST_FAILED", "Gemini request failed.")


def run(agent, request: str = "Review authentication"):
    return asyncio.run(agent.analyze(request, CONTEXT))


def test_review_finding_accepts_valid_data() -> None:
    finding = ReviewFinding.model_validate(finding_payload())

    assert finding.category == "security"
    assert finding.severity == "high"


@pytest.mark.parametrize(
    "field,value",
    [("category", "architecture"), ("severity", "urgent")],
)
def test_review_finding_rejects_invalid_controlled_values(field: str, value: str) -> None:
    payload = finding_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ReviewFinding.model_validate(payload)


def test_review_finding_rejects_missing_required_fields() -> None:
    payload = finding_payload()
    del payload["recommendation"]

    with pytest.raises(ValidationError):
        ReviewFinding.model_validate(payload)


@pytest.mark.parametrize(
    ("agent_type", "category"),
    [
        (SecurityAgent, "security"),
        (CodeQualityAgent, "quality"),
        (PerformanceAgent, "performance"),
    ],
)
def test_specialist_returns_valid_structured_findings(agent_type, category: str) -> None:
    gemini = FakeGemini(json.dumps({"findings": [finding_payload(category)]}))
    agent = agent_type(gemini)

    result = run(agent)

    assert isinstance(result, AgentAnalysis)
    assert result.findings[0].category == category
    assert "src/auth.py" in gemini.prompts[0]
    assert "Review authentication" in gemini.prompts[0]


@pytest.mark.parametrize("agent_type", [SecurityAgent, CodeQualityAgent, PerformanceAgent])
def test_specialists_support_no_findings(agent_type) -> None:
    result = run(agent_type(FakeGemini('{"findings": []}')))

    assert result.findings == []


@pytest.mark.parametrize("agent_type", [SecurityAgent, CodeQualityAgent, PerformanceAgent])
def test_specialists_reject_malformed_json(agent_type) -> None:
    with pytest.raises(AgentException) as raised:
        run(agent_type(FakeGemini("not json")))

    assert raised.value.code == "MALFORMED_AGENT_RESPONSE"


@pytest.mark.parametrize("agent_type", [SecurityAgent, CodeQualityAgent, PerformanceAgent])
def test_specialists_wrap_gemini_failures(agent_type) -> None:
    with pytest.raises(AgentException) as raised:
        run(agent_type(FailingGemini()))

    assert raised.value.code == "GEMINI_REQUEST_FAILED"


def test_agent_runs_sync_gemini_call_in_worker_thread() -> None:
    gemini = FakeGemini()
    caller_thread = threading.get_ident()

    run(SecurityAgent(gemini))

    assert gemini.thread_ids[0] != caller_thread