from __future__ import annotations

from agent.orchestrator import GapHunterAgent, build_deterministic_result
from app.models import RunRequest, RunStatus
from app.storage import RunStore


def test_hello_returns_deterministic_message():
    agent = GapHunterAgent()

    assert agent.hello("GapHunter") == {"message": "hello GapHunter"}
    assert agent.query(name="GapHunter") == {"message": "hello GapHunter"}


def test_build_deterministic_result_is_schema_valid():
    result = build_deterministic_result("Swiss B2B workflows", started_at=0)

    assert result.status == RunStatus.COMPLETED
    assert result.mode == "agent_engine_spike"
    assert result.ideas[0].source_urls


def test_run_writes_completed_result_to_store():
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B workflows"))
    agent = GapHunterAgent(store)

    response = agent.run(queued.run_id, "Swiss B2B workflows", user_id="test-user")

    status = store.get_status(queued.run_id)
    assert response == {"run_id": queued.run_id, "status": "completed"}
    assert status.status == RunStatus.COMPLETED
    assert status.ideas[0].title == "Agent Engine Spike Brief"
    assert status.events[0].stage == "running"


def test_query_dispatches_to_run_when_run_id_and_prompt_are_present():
    store = RunStore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B workflows"))
    agent = GapHunterAgent(store)

    response = agent.query(run_id=queued.run_id, prompt="Swiss B2B workflows")

    assert response == {"run_id": queued.run_id, "status": "completed"}
