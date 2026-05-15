from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models import ProgressEvent, RunRequest, RunResult, RunStatus, RunStatusResponse, SourceEvidence
from app.settings import settings

logger = logging.getLogger(__name__)

_MAX_MEMORY_RUNS = 100
_TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.FAILED}


class InvalidRunStateError(RuntimeError):
    pass


class RunStore:
    def __init__(self) -> None:
        self._memory: OrderedDict[str, RunResult] = OrderedDict()
        self._run_docs: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._events: defaultdict[str, list[ProgressEvent]] = defaultdict(list)
        self._sources: defaultdict[str, list[SourceEvidence]] = defaultdict(list)
        self._idempotency_keys: dict[str, str] = {}
        self._firestore_client = None

        if settings.gcp_project_id:
            try:
                from google.cloud import firestore

                self._firestore_client = firestore.Client(project=settings.gcp_project_id)
            except Exception:
                logger.exception(
                    "Failed to initialize Firestore client for project %s",
                    settings.gcp_project_id,
                )
                raise

    def save(self, result: RunResult) -> RunResult:
        self._memory[result.id] = result
        self._run_docs[result.id] = self._doc_from_result(result)
        if len(self._memory) > _MAX_MEMORY_RUNS:
            stale_id, _ = self._memory.popitem(last=False)
            self._run_docs.pop(stale_id, None)
            self._events.pop(stale_id, None)
            self._sources.pop(stale_id, None)

        if self._firestore_client:
            self._firestore_client.collection(settings.firestore_collection).document(result.id).set(
                result.firestore_dict()
            )
        return result

    def get(self, run_id: str) -> RunResult | None:
        if run_id in self._memory:
            return self._memory[run_id]

        if not self._firestore_client:
            return None

        snapshot = (
            self._firestore_client.collection(settings.firestore_collection).document(run_id).get()
        )
        if not snapshot.exists:
            return None
        doc = snapshot.to_dict()
        if doc.get("status") != RunStatus.COMPLETED.value:
            return None
        return RunResult.model_validate(doc)

    def create_queued_run(self, request: RunRequest) -> RunStatusResponse:
        if request.idempotency_key:
            existing_id = self._idempotency_keys.get(request.idempotency_key)
            if existing_id:
                existing = self.get_status(existing_id)
                if existing:
                    return existing

            if self._firestore_client:
                existing = self._find_firestore_run_by_idempotency_key(request.idempotency_key)
                if existing:
                    return existing

        run_id = uuid4().hex
        created_at = datetime.now(timezone.utc)
        doc = {
            "schema_version": 1,
            "id": run_id,
            "run_id": run_id,
            "status": RunStatus.QUEUED.value,
            "created_at": created_at.isoformat(),
            "prompt": request.prompt,
            "idempotency_key": request.idempotency_key,
            "event_sequence": 0,
            "progress": "queued",
        }

        self._run_docs[run_id] = doc
        self._remember_idempotency_key(request.idempotency_key, run_id)
        self._evict_if_needed()

        if self._firestore_client:
            self._run_ref(run_id).set(doc)

        return self.get_status(run_id) or self._response_from_doc(doc)

    def mark_running(self, run_id: str) -> RunStatusResponse:
        self._transition(run_id, RunStatus.RUNNING, allowed={RunStatus.QUEUED}, progress="running")
        return self._require_status(run_id)

    def complete_with_result(self, run_id: str, result: RunResult) -> RunStatusResponse:
        current = self.get_status(run_id)
        if not current:
            raise KeyError(f"Run {run_id} not found")
        if current.status != RunStatus.RUNNING:
            raise InvalidRunStateError(
                f"Run {run_id} must be running before completion; current status is {current.status}"
            )

        completed = result.model_copy(update={"id": run_id, "status": RunStatus.COMPLETED})
        completed_doc = self._doc_from_result(completed) | {"progress": "completed"}
        if self._firestore_client:
            self._firestore_conditional_update(run_id, completed_doc, allowed={RunStatus.RUNNING})

        self._memory[run_id] = completed
        self._run_docs[run_id].update(completed_doc)
        self._evict_if_needed()

        return self._require_status(run_id)

    def fail_with_error(self, run_id: str, error: str) -> RunStatusResponse:
        current = self.get_status(run_id)
        if not current:
            raise KeyError(f"Run {run_id} not found")
        if current.status in _TERMINAL_STATUSES:
            raise InvalidRunStateError(
                f"Run {run_id} is already terminal; current status is {current.status}"
            )

        safe_error = error.strip()[:500] or "Run failed"
        self._update_run_doc(
            run_id,
            {"status": RunStatus.FAILED.value, "error": safe_error, "progress": "failed"},
            allowed={RunStatus.QUEUED, RunStatus.RUNNING},
        )
        return self._require_status(run_id)

    def append_event(self, run_id: str, stage: str, message: str) -> ProgressEvent:
        if not self.get_status(run_id):
            raise KeyError(f"Run {run_id} not found")

        sequence = len(self._events[run_id]) + 1
        event = ProgressEvent(
            id=f"{sequence:06d}",
            sequence=sequence,
            stage=stage,
            message=message,
        )
        self._events[run_id].append(event)
        self._update_run_doc(run_id, {"event_sequence": sequence, "progress": stage})

        if self._firestore_client:
            self._run_ref(run_id).collection("events").document(event.id).set(
                event.model_dump(mode="json")
            )

        return event

    def append_source(self, run_id: str, source: SourceEvidence) -> SourceEvidence:
        if not self.get_status(run_id):
            raise KeyError(f"Run {run_id} not found")

        self._sources[run_id].append(source)
        if self._firestore_client:
            self._run_ref(run_id).collection("sources").document(source.id).set(
                source.model_dump(mode="json")
            )
        return source

    def get_events(self, run_id: str) -> list[ProgressEvent] | None:
        if not self.get_status(run_id):
            return None

        if run_id in self._events and self._events[run_id]:
            return list(self._events[run_id])

        if self._firestore_client:
            events = [
                ProgressEvent.model_validate(snapshot.to_dict())
                for snapshot in self._run_ref(run_id).collection("events").order_by("sequence").stream()
            ]
            self._events[run_id].extend(events)
            return events

        return []

    def get_status(self, run_id: str) -> RunStatusResponse | None:
        cached = self._run_docs.get(run_id)
        # For non-terminal states, always re-read from Firestore so Agent Engine
        # writes are visible without waiting for local state transitions.
        if cached is not None and RunStatus(cached["status"]) not in _TERMINAL_STATUSES:
            if self._firestore_client:
                return self._fetch_from_firestore(run_id)
            return self._response_from_doc(cached)

        if cached is not None:
            return self._response_from_doc(cached)

        if self._firestore_client:
            return self._fetch_from_firestore(run_id)

        result = self.get(run_id)
        if result:
            return RunStatusResponse.from_result(result, events=self._events[run_id])

        return None

    def _fetch_from_firestore(self, run_id: str) -> RunStatusResponse | None:
        snapshot = self._run_ref(run_id).get()
        if not snapshot.exists:
            return None
        doc = snapshot.to_dict()
        self._run_docs[run_id] = doc
        # Load events from Firestore subcollection if not cached locally.
        if not self._events[run_id]:
            fs_events = [
                ProgressEvent.model_validate(e.to_dict())
                for e in self._run_ref(run_id).collection("events").order_by("sequence").stream()
            ]
            self._events[run_id].extend(fs_events)
        return self._response_from_doc(doc)

    def _transition(
        self,
        run_id: str,
        next_status: RunStatus,
        *,
        allowed: set[RunStatus],
        progress: str,
    ) -> None:
        current = self.get_status(run_id)
        if not current:
            raise KeyError(f"Run {run_id} not found")
        if current.status not in allowed:
            raise InvalidRunStateError(
                f"Run {run_id} cannot transition from {current.status} to {next_status}"
            )
        self._update_run_doc(
            run_id,
            {"status": next_status.value, "progress": progress},
            allowed=allowed,
        )

    def _update_run_doc(
        self,
        run_id: str,
        fields: dict[str, Any],
        *,
        allowed: set[RunStatus] | None = None,
    ) -> None:
        if self._firestore_client and allowed is not None:
            self._firestore_conditional_update(run_id, fields, allowed=allowed)
        elif self._firestore_client:
            self._run_ref(run_id).update(fields)

        if run_id in self._run_docs:
            self._run_docs[run_id].update(fields)
        elif run_id in self._memory:
            self._run_docs[run_id] = self._doc_from_result(self._memory[run_id]) | fields
        else:
            raise KeyError(f"Run {run_id} not found")

    def _response_from_doc(self, doc: dict[str, Any]) -> RunStatusResponse:
        status = RunStatus(doc["status"])
        run_id = doc.get("run_id") or doc["id"]
        if status == RunStatus.COMPLETED and doc.get("constraints") is not None:
            result = RunResult.model_validate(doc)
            return RunStatusResponse.from_result(
                result,
                events=self._events[run_id],
                progress=doc.get("progress"),
            )

        return RunStatusResponse(
            schema_version=doc.get("schema_version", 1),
            id=run_id,
            run_id=run_id,
            status=status,
            created_at=doc.get("created_at"),
            events=self._events[run_id],
            progress=doc.get("progress"),
            error=doc.get("error"),
        )

    def _doc_from_result(self, result: RunResult) -> dict[str, Any]:
        doc = result.firestore_dict()
        doc["run_id"] = result.id
        doc.setdefault("progress", result.status.value)
        doc.setdefault("event_sequence", len(self._events[result.id]))
        return doc

    def _remember_idempotency_key(self, key: str | None, run_id: str) -> None:
        if key:
            self._idempotency_keys[key] = run_id

    def _evict_if_needed(self) -> None:
        while len(self._run_docs) > _MAX_MEMORY_RUNS:
            stale_id, stale_doc = self._run_docs.popitem(last=False)
            self._memory.pop(stale_id, None)
            self._events.pop(stale_id, None)
            self._sources.pop(stale_id, None)
            idempotency_key = stale_doc.get("idempotency_key")
            if idempotency_key:
                self._idempotency_keys.pop(idempotency_key, None)

    def _require_status(self, run_id: str) -> RunStatusResponse:
        status = self.get_status(run_id)
        if not status:
            raise KeyError(f"Run {run_id} not found")
        return status

    def _run_ref(self, run_id: str):
        return self._firestore_client.collection(settings.firestore_collection).document(run_id)

    def _find_firestore_run_by_idempotency_key(self, idempotency_key: str) -> RunStatusResponse | None:
        query = (
            self._firestore_client.collection(settings.firestore_collection)
            .where("idempotency_key", "==", idempotency_key)
            .limit(1)
        )
        for snapshot in query.stream():
            if snapshot.exists:
                doc = snapshot.to_dict()
                self._run_docs[doc.get("run_id") or doc["id"]] = doc
                return self._response_from_doc(doc)
        return None

    def _firestore_conditional_update(
        self,
        run_id: str,
        fields: dict[str, Any],
        *,
        allowed: set[RunStatus],
    ) -> None:
        from google.cloud import firestore

        ref = self._run_ref(run_id)
        transaction = self._firestore_client.transaction()

        @firestore.transactional
        def update_in_transaction(transaction):
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                raise KeyError(f"Run {run_id} not found")
            current_status = RunStatus(snapshot.to_dict()["status"])
            if current_status not in allowed:
                raise InvalidRunStateError(
                    f"Run {run_id} cannot be updated from status {current_status}"
                )
            transaction.update(ref, fields)

        update_in_transaction(transaction)


store = RunStore()
