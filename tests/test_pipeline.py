from types import SimpleNamespace

from app.models import RunRequest, SearchResult
from app.main import create_run, health, logo
from app.pipeline import build_job_query, parse_constraints, run_pipeline


def test_parse_constraints_extracts_common_hints() -> None:
    constraints = parse_constraints("Swiss fintech workflows, high complexity, exclude lending")

    assert constraints.geography == "Switzerland"
    assert constraints.industry == "Financial services"
    assert constraints.complexity_threshold == "high"
    assert constraints.exclusions == ["lending"]


def test_run_pipeline_returns_source_backed_ideas() -> None:
    result = run_pipeline(RunRequest(prompt="Swiss B2B workflows with digital inputs"))

    assert result.status == "completed"
    assert result.mode in {"demo", "live_search"}
    assert result.ideas
    assert all(idea.source_urls for idea in result.ideas)
    assert all(idea.critique.objections for idea in result.ideas)


def test_route_functions_work_without_network() -> None:
    assert health()["status"] == "ok"
    assert create_run(RunRequest(prompt="Swiss B2B workflows")).ideas
    assert logo().media_type == "image/svg+xml"


def test_build_job_query_includes_constraint_signals() -> None:
    constraints = parse_constraints("Swiss fintech workflows, high complexity")

    query = build_job_query(constraints)

    assert "Switzerland" in query
    assert "Financial services" in query
    assert "senior specialist analyst" in query


def test_live_search_pipeline_uses_search_results(monkeypatch) -> None:
    monkeypatch.setattr("app.pipeline.settings", SimpleNamespace(live_research_enabled=True))

    def fake_job_search(query: str, *, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title="Tender Operations Specialist",
                snippet="Reviews incoming tenders and prepares qualification memos.",
                url="https://example.com/jobs/tender-ops",
            )
        ]

    def fake_competitor_search(query: str, *, limit: int = 5) -> list[SearchResult]:
        return []

    monkeypatch.setattr("app.pipeline.job_search", fake_job_search)
    monkeypatch.setattr("app.pipeline.competitor_search", fake_competitor_search)

    result = run_pipeline(RunRequest(prompt="Swiss B2B workflows with digital inputs"))

    assert result.mode == "live_search"
    assert result.ideas[0].job_being_replaced == "Tender Operations Specialist"
    assert str(result.ideas[0].source_urls[0]) == "https://example.com/jobs/tender-ops"
