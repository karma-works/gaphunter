from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

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


def test_agent_engine_gateway_start_run_enqueues_cloud_task(monkeypatch):
    created_tasks = []

    class _FakeTasksClient:
        def create_task(self, *, parent, task):
            created_tasks.append({"parent": parent, "task": task})

    monkeypatch.setattr("google.cloud.tasks_v2.CloudTasksClient", _FakeTasksClient)

    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    gateway = AgentEngineGateway(
        "projects/123/locations/us-central1/reasoningEngines/456",
        store,
        queue="projects/123/locations/us-central1/queues/gaphunter-agent-engine",
        service_url="https://gaphunter.example.com",
        tasks_sa="tasks-invoker@project.iam.gserviceaccount.com",
    )

    gateway.start_run(queued.run_id, RunRequest(prompt="Swiss B2B"))

    assert len(created_tasks) == 1
    http_req = created_tasks[0]["task"].http_request
    assert http_req.url == "https://gaphunter.example.com/internal/tasks/run-agent"
    body = json.loads(http_req.body)
    assert body["run_id"] == queued.run_id
    assert body["prompt"] == "Swiss B2B"
    assert http_req.oidc_token.service_account_email == "tasks-invoker@project.iam.gserviceaccount.com"
    assert http_req.oidc_token.audience == "https://gaphunter.example.com"


def test_agent_engine_gateway_start_run_raises_without_cloud_tasks_config():
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    gateway = AgentEngineGateway("fake-resource", store)

    with pytest.raises(ValueError, match="CLOUD_TASKS_QUEUE"):
        gateway.start_run(queued.run_id, RunRequest(prompt="Swiss B2B"))


# ---------------------------------------------------------------------------
# /internal/tasks/run-agent route
# ---------------------------------------------------------------------------

def _make_agent_engine_gateway(store: RunStore) -> AgentEngineGateway:
    return AgentEngineGateway(
        "projects/123/locations/us-central1/reasoningEngines/456",
        store,
        queue="projects/123/locations/us-central1/queues/gaphunter-agent-engine",
        service_url="https://gaphunter.example.com",
        tasks_sa="tasks-invoker@project.iam.gserviceaccount.com",
    )


def test_run_agent_task_route_calls_invoke(monkeypatch):
    import app.main as main_module
    from app.settings import Settings

    invoked = []
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    agent_gw = _make_agent_engine_gateway(store)
    monkeypatch.setattr(agent_gw, "_invoke", lambda run_id, req: invoked.append((run_id, req.prompt)))
    monkeypatch.setattr(main_module, "gateway", agent_gw)
    monkeypatch.setattr(main_module, "store", store)
    # gcp_project_id=None → OIDC verification is skipped
    monkeypatch.setattr(main_module, "settings", Settings(gcp_project_id=None))

    client = TestClient(main_module.app)
    response = client.post(
        "/internal/tasks/run-agent",
        json={"run_id": queued.run_id, "prompt": "Swiss B2B"},
    )

    assert response.status_code == 200
    assert response.json()["run_id"] == queued.run_id
    assert invoked == [(queued.run_id, "Swiss B2B")]


def test_run_agent_task_route_returns_400_for_missing_payload(monkeypatch):
    import app.main as main_module
    from app.settings import Settings

    monkeypatch.setattr(main_module, "settings", Settings(gcp_project_id=None))

    client = TestClient(main_module.app)
    response = client.post("/internal/tasks/run-agent", json={"run_id": "only-run-id"})

    assert response.status_code == 400


def test_run_agent_task_route_returns_400_when_not_agent_engine_backend(monkeypatch):
    import app.main as main_module
    from app.agent_gateway import LocalPipelineAgentGateway
    from app.settings import Settings

    store = RunStore()
    monkeypatch.setattr(main_module, "gateway", LocalPipelineAgentGateway(store))
    monkeypatch.setattr(main_module, "settings", Settings(gcp_project_id=None))

    client = TestClient(main_module.app)
    response = client.post(
        "/internal/tasks/run-agent",
        json={"run_id": "r1", "prompt": "Swiss B2B"},
    )

    assert response.status_code == 400


def test_run_agent_task_route_requires_oidc_token_in_gcp(monkeypatch):
    import app.main as main_module
    from app.settings import Settings

    store = RunStore()
    agent_gw = _make_agent_engine_gateway(store)
    monkeypatch.setattr(main_module, "gateway", agent_gw)
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(
            gcp_project_id="fake-project",
            cloud_run_service_url="https://gaphunter.example.com",
        ),
    )

    client = TestClient(main_module.app, raise_server_exceptions=False)
    response = client.post(
        "/internal/tasks/run-agent",
        json={"run_id": "r1", "prompt": "Swiss B2B"},
    )

    assert response.status_code == 401
