from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models import (
    ConstraintSet,
    Critique,
    Evidence,
    IdeaBrief,
    RunRequest,
    RunResult,
    RunStatus,
    SourceEvidence,
)


def _make_result(run_id: str = "abc123") -> RunResult:
    return RunResult(
        id=run_id,
        status=RunStatus.COMPLETED,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        constraints=ConstraintSet(raw_prompt="Swiss B2B"),
        ideas=[
            IdeaBrief(
                title="Test Agent",
                one_liner="Automates test work.",
                target_customer="B2B teams",
                job_being_replaced="Test Analyst",
                gap_evidence=[
                    Evidence(
                        label="Source",
                        url="https://example.com",
                        note="Test note",
                    )
                ],
                source_urls=["https://example.com"],
                ai_feasibility_note="Feasible.",
                critique=Critique(objections=["Objection 1"], severity="low"),
                research_coverage_score=0.7,
                score_rationale="Test score.",
            )
        ],
        run_duration_s=1.0,
        mode="demo",
    )


def _make_store_no_firestore():
    with patch("app.storage.settings", SimpleNamespace(gcp_project_id=None, firestore_collection="runs")):
        from app.storage import RunStore
        return RunStore()


def test_save_and_get_in_memory():
    store = _make_store_no_firestore()
    result = _make_result("run1")

    store.save(result)

    assert store.get("run1") == result


def test_get_returns_none_for_missing_run():
    store = _make_store_no_firestore()

    assert store.get("nonexistent") is None


def test_lru_eviction_keeps_max_100():
    store = _make_store_no_firestore()

    for i in range(105):
        store.save(_make_result(f"run{i:03d}"))

    assert len(store._memory) == 100
    assert store.get("run000") is None
    assert store.get("run004") is None
    assert store.get("run005") is not None
    assert store.get("run104") is not None


def test_save_writes_to_firestore_when_configured():
    mock_client = MagicMock()
    mock_doc = MagicMock()
    mock_client.collection.return_value.document.return_value = mock_doc

    with patch("app.storage.settings", SimpleNamespace(gcp_project_id="proj", firestore_collection="runs")):
        with patch("google.cloud.firestore.Client", return_value=mock_client):
            from importlib import reload
            import app.storage
            reload(app.storage)
            store = app.storage.RunStore()

    result = _make_result("run1")
    store._firestore_client = mock_client
    store.save(result)

    mock_client.collection.assert_called_with("runs")
    mock_doc.set.assert_called_once_with(result.firestore_dict())


def test_get_reads_from_firestore_when_not_in_memory():
    mock_client = MagicMock()
    result = _make_result("run1")

    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.to_dict.return_value = result.firestore_dict()
    mock_client.collection.return_value.document.return_value.get.return_value = mock_snapshot

    store = _make_store_no_firestore()
    store._firestore_client = mock_client

    loaded = store.get("run1")

    assert loaded is not None
    assert loaded.id == "run1"
    mock_client.collection.assert_called_with("runs")


def test_get_returns_none_when_firestore_doc_missing():
    mock_client = MagicMock()
    mock_snapshot = MagicMock()
    mock_snapshot.exists = False
    mock_client.collection.return_value.document.return_value.get.return_value = mock_snapshot

    store = _make_store_no_firestore()
    store._firestore_client = mock_client

    assert store.get("missing") is None


def test_firestore_write_failure_raises():
    mock_client = MagicMock()
    mock_client.collection.return_value.document.return_value.set.side_effect = RuntimeError("write failed")

    store = _make_store_no_firestore()
    store._firestore_client = mock_client

    result = _make_result("run1")
    with pytest.raises(RuntimeError, match="write failed"):
        store.save(result)


def test_create_queued_run_and_mark_running():
    store = _make_store_no_firestore()

    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))

    assert queued.status == RunStatus.QUEUED
    assert queued.run_id == queued.id

    running = store.mark_running(queued.run_id)

    assert running.status == RunStatus.RUNNING
    assert running.progress == "running"


def test_complete_with_result_requires_running_state():
    store = _make_store_no_firestore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))

    with pytest.raises(RuntimeError):
        store.complete_with_result(queued.run_id, _make_result())

    store.mark_running(queued.run_id)
    completed = store.complete_with_result(queued.run_id, _make_result("different-id"))

    assert completed.status == RunStatus.COMPLETED
    assert completed.run_id == queued.run_id
    assert completed.ideas
    assert store.get(queued.run_id) is not None


def test_terminal_run_cannot_be_failed_or_completed_again():
    store = _make_store_no_firestore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))
    store.mark_running(queued.run_id)
    store.complete_with_result(queued.run_id, _make_result())

    with pytest.raises(RuntimeError):
        store.fail_with_error(queued.run_id, "late failure")

    with pytest.raises(RuntimeError):
        store.complete_with_result(queued.run_id, _make_result())


def test_failed_status_response_is_safe_and_terminal():
    store = _make_store_no_firestore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))

    failed = store.fail_with_error(queued.run_id, "  search provider unavailable  ")

    assert failed.status == RunStatus.FAILED
    assert failed.error == "search provider unavailable"

    with pytest.raises(RuntimeError):
        store.mark_running(queued.run_id)


def test_idempotency_key_reuses_existing_run():
    store = _make_store_no_firestore()
    request = RunRequest(prompt="Swiss B2B", idempotency_key="idem-1")

    first = store.create_queued_run(request)
    second = store.create_queued_run(request)

    assert second.run_id == first.run_id


def test_append_event_uses_monotonic_zero_padded_ids():
    store = _make_store_no_firestore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))

    first = store.append_event(queued.run_id, "parsing_constraints", "Parsing constraints.")
    second = store.append_event(queued.run_id, "researching_jobs", "Researching jobs.")
    status = store.get_status(queued.run_id)

    assert first.id == "000001"
    assert second.id == "000002"
    assert [event.id for event in status.events] == ["000001", "000002"]
    assert status.progress == "researching_jobs"
    assert [event.id for event in store.get_events(queued.run_id)] == ["000001", "000002"]


def test_get_events_returns_none_for_missing_run():
    store = _make_store_no_firestore()

    assert store.get_events("missing") is None


def test_append_source_requires_existing_run():
    store = _make_store_no_firestore()
    queued = store.create_queued_run(RunRequest(prompt="Swiss B2B"))

    source = store.append_source(
        queued.run_id,
        SourceEvidence(
            url="https://example.com/source",
            title="Source",
            snippet="Evidence",
            provider="brave",
            query="Swiss B2B",
        ),
    )

    assert str(source.url) == "https://example.com/source"

    with pytest.raises(KeyError):
        store.append_source("missing", source)
