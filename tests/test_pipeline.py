from types import SimpleNamespace

from app.models import RunRequest, SearchResult
from app.main import create_run, health, logo
from app.pipeline import build_job_query, parse_constraints, run_pipeline
from app.search import brave_search


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


def test_run_pipeline_falls_back_to_demo_on_search_error(monkeypatch) -> None:
    monkeypatch.setattr("app.pipeline.settings", SimpleNamespace(live_research_enabled=True))
    monkeypatch.setattr("app.pipeline.job_search", lambda *a, **kw: (_ for _ in ()).throw(
        __import__("app.search", fromlist=["SearchError"]).SearchError("API down")
    ))

    result = run_pipeline(RunRequest(prompt="Swiss B2B workflows"))

    assert result.mode == "demo"
    assert result.ideas


def test_synthesize_live_ideas_with_competitors_found(monkeypatch) -> None:
    from app.models import JobCandidate, CompetitorCheckResult
    from app.pipeline import synthesize_live_ideas

    candidate = JobCandidate(
        title="Tender Ops Specialist",
        description="Reviews tenders.",
        source_url="https://example.com/job",
    )
    check = CompetitorCheckResult(
        job_title="Tender Ops Specialist",
        competitors_found=[
            SearchResult(title="CompetitorA", snippet="Does this.", url="https://comp.example.com"),
            SearchResult(title="CompetitorB", snippet="Does that.", url="https://comp2.example.com"),
        ],
        gap_confirmed=False,
        coverage_note="Checked via Brave.",
    )

    ideas = synthesize_live_ideas([candidate], [check])

    assert len(ideas) == 1
    assert ideas[0].research_coverage_score < 0.72
    assert ideas[0].research_coverage_score >= 0.35


def test_brave_search_normalizes_web_results(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.search.settings",
        SimpleNamespace(
            brave_search_api_key="test-key",
            brave_search_country="US",
            brave_search_lang="en",
        ),
    )

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {
                "web": {
                    "results": [
                        {
                            "title": "Tender Operations Specialist",
                            "url": "https://example.com/jobs/tender-ops",
                            "description": "Reviews incoming tenders.",
                            "extra_snippets": ["Drafts bid/no-bid memos."],
                        },
                        {
                            "title": "Missing URL",
                            "description": "This result is dropped.",
                        },
                    ]
                }
            }

    captured: dict = {}

    def fake_get(url: str, **kwargs) -> FakeResponse:
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.search.httpx.get", fake_get)

    results = brave_search("tender operations", limit=30)

    assert captured["url"] == "https://api.search.brave.com/res/v1/web/search"
    assert captured["headers"]["X-Subscription-Token"] == "test-key"
    assert captured["params"]["count"] == 20
    assert results == [
        SearchResult(
            title="Tender Operations Specialist",
            snippet="Reviews incoming tenders. Drafts bid/no-bid memos.",
            url="https://example.com/jobs/tender-ops",
        )
    ]
