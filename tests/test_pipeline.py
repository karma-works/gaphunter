from app.models import RunRequest
from app.main import create_run, health, logo
from app.pipeline import parse_constraints, run_pipeline


def test_parse_constraints_extracts_common_hints() -> None:
    constraints = parse_constraints("Swiss fintech workflows, high complexity, exclude lending")

    assert constraints.geography == "Switzerland"
    assert constraints.industry == "Financial services"
    assert constraints.complexity_threshold == "high"
    assert constraints.exclusions == ["lending"]


def test_run_pipeline_returns_source_backed_ideas() -> None:
    result = run_pipeline(RunRequest(prompt="Swiss B2B workflows with digital inputs"))

    assert result.status == "completed"
    assert result.mode in {"demo", "live"}
    assert result.ideas
    assert all(idea.source_urls for idea in result.ideas)
    assert all(idea.critique.objections for idea in result.ideas)


def test_route_functions_work_without_network() -> None:
    assert health()["status"] == "ok"
    assert create_run(RunRequest(prompt="Swiss B2B workflows")).ideas
    assert logo().media_type == "image/svg+xml"
