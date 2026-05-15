from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.agent_gateway import AgentEngineGateway, FakeAgentGateway, LocalPipelineAgentGateway, build_agent_gateway
from app.models import ConstraintSet, Critique, Evidence, IdeaBrief, RunRequest, RunResult, RunStatus
from app.storage import RunStore


def _make_result(run_id: str = "result-id") -> RunResult:
    return RunResult(
        id=run_id,
        status=RunStatus.COMPLETED,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        constraints=ConstraintSet(raw_prompt="Swiss B2B"),
        ideas=[
            IdeaBrief(
                title="Gateway Agent",
                one_liner="Automates gateway work.",
                target_customer="B2B teams",
                job_being_replaced="Gateway Analyst",
                gap_evidence=[
                    Evidence(label="Source", url="https://example.com", note="Test note")
                ],
                source_urls=["https://example.com"],
                ai_feasibility_note="Feasible.",
                critique=Critique(objections=["Objection"], severity="low"),
                research_coverage_score=0.7,
                score_rationale="Test score.",
            )
        ],
        run_duration_s=0.1,
        mode="test",
    )


def test_local_gateway_completes_queued_run():
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    gateway = LocalPipelineAgentGateway(store, pipeline=lambda request: _make_result())

    gateway.start_run(queued.run_id, RunRequest(prompt="Swiss B2B"))

    status = store.get_status(queued.run_id)
    assert status.status == RunStatus.COMPLETED
    assert status.ideas[0].title == "Gateway Agent"
    assert [event.id for event in status.events] == ["000001"]


def test_local_gateway_marks_failed_on_pipeline_error():
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))

    def fail_pipeline(request: RunRequest) -> RunResult:
        raise RuntimeError("pipeline exploded")

    gateway = LocalPipelineAgentGateway(store, pipeline=fail_pipeline)

    gateway.start_run(queued.run_id, RunRequest(prompt="Swiss B2B"))

    status = store.get_status(queued.run_id)
    assert status.status == RunStatus.FAILED
    assert status.error == "pipeline exploded"


def test_fake_gateway_uses_canned_result():
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    gateway = FakeAgentGateway(store, result=_make_result())

    gateway.start_run(queued.run_id, RunRequest(prompt="Swiss B2B"))

    assert store.get_status(queued.run_id).status == RunStatus.COMPLETED


def test_fake_gateway_can_fail():
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    gateway = FakeAgentGateway(store, error="fake failure")

    gateway.start_run(queued.run_id, RunRequest(prompt="Swiss B2B"))

    status = store.get_status(queued.run_id)
    assert status.status == RunStatus.FAILED
    assert status.error == "fake failure"


def test_build_agent_gateway_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unsupported AGENT_BACKEND"):
        build_agent_gateway("missing", RunStore())


def test_agent_engine_backend_requires_resource_name():
    with pytest.raises(ValueError, match="AGENT_ENGINE_RESOURCE_NAME"):
        build_agent_gateway("agent_engine", RunStore())


def test_agent_engine_gateway_invoke_calls_remote_agent(monkeypatch):
    calls = []

    class _FakeRemoteAgent:
        def query(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr("vertexai.agent_engines.get", lambda name: _FakeRemoteAgent())

    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    gateway = AgentEngineGateway(
        "projects/123/locations/us-central1/reasoningEngines/456",
        store,
        max_search_queries=5,
        max_gemini_calls=10,
    )

    gateway._invoke(queued.run_id, RunRequest(prompt="Swiss B2B"))

    assert calls[0]["run_id"] == queued.run_id
    assert calls[0]["prompt"] == "Swiss B2B"
    assert calls[0]["max_search_queries"] == 5
    assert calls[0]["max_gemini_calls"] == 10


def test_agent_engine_gateway_writes_failed_on_invocation_error(monkeypatch):
    monkeypatch.setattr(
        "vertexai.agent_engines.get",
        lambda name: (_ for _ in ()).throw(RuntimeError("network error")),
    )

    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    gateway = AgentEngineGateway("fake-resource", store)

    gateway._invoke(queued.run_id, RunRequest(prompt="Swiss B2B"))

    status = store.get_status(queued.run_id)
    assert status.status == RunStatus.FAILED
    assert "network error" in status.error


def test_agent_engine_gateway_start_run_spawns_thread(monkeypatch):
    import threading

    invoked = threading.Event()

    def fake_invoke(run_id, request):
        invoked.set()

    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    gateway = AgentEngineGateway("fake-resource", store)
    monkeypatch.setattr(gateway, "_invoke", fake_invoke)

    gateway.start_run(queued.run_id, RunRequest(prompt="Swiss B2B"))

    assert invoked.wait(timeout=2)
