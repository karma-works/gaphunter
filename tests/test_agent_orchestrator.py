from __future__ import annotations

import pytest

from agent.orchestrator import (
    GapHunterAgent,
    _RunBudget,
    _candidates_to_ideas_and_sources,
    _regex_parse_constraints,
    _results_to_candidates,
    build_deterministic_result,
)
from app.models import RunRequest, RunStatus
from app.storage import RunStore


# ---------------------------------------------------------------------------
# _RunBudget kill switch
# ---------------------------------------------------------------------------

def test_run_budget_consume_search_raises_when_exhausted():
    budget = _RunBudget(max_search_queries=2, max_gemini_calls=50)
    budget.consume_search()
    budget.consume_search()

    with pytest.raises(RuntimeError, match="search query budget exhausted"):
        budget.consume_search()


def test_run_budget_consume_gemini_raises_when_exhausted():
    budget = _RunBudget(max_search_queries=20, max_gemini_calls=1)
    budget.consume_gemini()

    with pytest.raises(RuntimeError, match="Gemini call budget exhausted"):
        budget.consume_gemini()


# ---------------------------------------------------------------------------
# Spike / deterministic fallback
# ---------------------------------------------------------------------------

def test_build_deterministic_result_is_schema_valid():
    result = build_deterministic_result("Swiss B2B workflows", started_at=0)

    assert result.status == RunStatus.COMPLETED
    assert result.mode == "agent_engine_spike"
    assert result.ideas[0].source_urls


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def test_regex_parse_constraints_extracts_geography():
    c = _regex_parse_constraints("Swiss B2B workflows with high complexity")

    assert c["geography"] == "Switzerland"
    assert c["complexity_threshold"] == "high"
    assert c["raw_prompt"].startswith("Swiss")


def test_results_to_candidates_drops_url_less_results():
    results = [
        {"title": "Analyst", "url": "https://example.com/job1", "snippet": "desc"},
        {"title": "No URL job", "url": None, "snippet": "desc"},
        {"title": "Empty URL", "url": "", "snippet": "desc"},
    ]
    candidates = _results_to_candidates(results, {"industry": "Finance", "io_type": "digital"})

    assert len(candidates) == 1
    assert candidates[0]["title"] == "Analyst"
    assert candidates[0]["source_url"] == "https://example.com/job1"


def test_candidates_to_ideas_and_sources_all_ideas_have_source_urls():
    candidates = [
        {
            "title": "Compliance Analyst",
            "description": "Reviews regulatory documents.",
            "industry": "Finance",
            "source_url": "https://example.com/job1",
            "io_type": "digital",
            "complexity_signal": "high",
            "query": "Switzerland B2B",
        }
    ]
    ideas, sources = _candidates_to_ideas_and_sources(candidates)

    assert len(ideas) == 1
    assert len(sources) == 1
    assert ideas[0]["source_urls"] == ["https://example.com/job1"]
    assert sources[0]["url"] == "https://example.com/job1"


def test_candidates_to_ideas_caps_at_three():
    candidates = [
        {"title": f"Job {i}", "description": "desc", "source_url": f"https://example.com/{i}"}
        for i in range(5)
    ]
    ideas, sources = _candidates_to_ideas_and_sources(candidates)

    assert len(ideas) == 3
    assert len(sources) == 3


# ---------------------------------------------------------------------------
# GapHunterAgent — local store path (no API keys: spike fallback)
# ---------------------------------------------------------------------------

def test_hello_returns_deterministic_message():
    agent = GapHunterAgent()

    assert agent.hello("GapHunter") == {"message": "hello GapHunter"}
    assert agent.query(name="GapHunter") == {"message": "hello GapHunter"}


def test_run_falls_back_to_spike_without_brave_key(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B workflows"))
    agent = GapHunterAgent(store)

    response = agent.run(queued.run_id, "Swiss B2B workflows", user_id="test-user")

    status = store.get_status(queued.run_id)
    assert response == {"run_id": queued.run_id, "status": "completed"}
    assert status.status == RunStatus.COMPLETED
    assert status.ideas[0].title == "Agent Engine Spike Brief"
    assert status.events[0].stage == "running"


def test_run_accepts_budget_kwargs(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B workflows"))
    agent = GapHunterAgent(store)

    response = agent.run(
        queued.run_id, "Swiss B2B workflows",
        max_search_queries=5, max_gemini_calls=10,
    )

    assert response["status"] == "completed"


def test_query_dispatches_to_run(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B workflows"))
    agent = GapHunterAgent(store)

    response = agent.query(run_id=queued.run_id, prompt="Swiss B2B workflows")

    assert response == {"run_id": queued.run_id, "status": "completed"}


def test_query_passes_budget_kwargs_to_run(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B workflows"))
    agent = GapHunterAgent(store)

    response = agent.query(
        run_id=queued.run_id, prompt="Swiss B2B workflows",
        max_search_queries=5, max_gemini_calls=10,
    )

    assert response["status"] == "completed"


# ---------------------------------------------------------------------------
# GapHunterAgent — local store path with mocked Brave Search
# ---------------------------------------------------------------------------

def test_run_with_brave_search_produces_source_backed_ideas(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "fake-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    fake_results = [
        {
            "title": "Compliance Intake Analyst",
            "url": "https://example.com/job1",
            "snippet": "Reviews regulatory submissions for Swiss financial institutions.",
            "query": "Switzerland B2B compliance",
        },
        {
            "title": "RFP Coordinator",
            "url": "https://example.com/job2",
            "snippet": "Manages bid qualification for public tenders.",
            "query": "Switzerland B2B compliance",
        },
    ]
    monkeypatch.setattr("agent.tools.search.brave_search", lambda *a, **kw: fake_results)

    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B workflows"))
    agent = GapHunterAgent(store)

    response = agent.run(queued.run_id, "Swiss B2B workflows")

    status = store.get_status(queued.run_id)
    assert response["status"] == "completed"
    assert status.status == RunStatus.COMPLETED
    assert len(status.ideas) == 2
    for idea in status.ideas:
        assert idea.source_urls, "Every idea must have at least one source URL"
    stages = [e.stage for e in status.events]
    assert "parsing_constraints" in stages
    assert "researching_jobs" in stages
    assert "synthesizing_ideas" in stages


def test_run_fails_when_search_returns_no_candidates(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "fake-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("agent.tools.search.brave_search", lambda *a, **kw: [])

    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B workflows"))
    agent = GapHunterAgent(store)

    response = agent.run(queued.run_id, "Swiss B2B workflows")

    status = store.get_status(queued.run_id)
    assert response["status"] == "failed"
    assert status.status == RunStatus.FAILED
    assert "No source-backed" in status.error


def test_constraint_agent_uses_regex_without_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    agent = GapHunterAgent()
    budget = _RunBudget()

    constraints = agent._constraint_agent("Swiss B2B high complexity workflows", budget)

    assert constraints["geography"] == "Switzerland"
    assert constraints["complexity_threshold"] == "high"
    assert budget.gemini_calls_used == 0
