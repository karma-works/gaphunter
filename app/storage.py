from __future__ import annotations

from app.models import RunResult
from app.settings import settings


class RunStore:
    def __init__(self) -> None:
        self._memory: dict[str, RunResult] = {}
        self._firestore_client = None

        if settings.gcp_project_id:
            try:
                from google.cloud import firestore

                self._firestore_client = firestore.Client(project=settings.gcp_project_id)
            except Exception:
                self._firestore_client = None

    def save(self, result: RunResult) -> RunResult:
        self._memory[result.id] = result
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
        return RunResult.model_validate(snapshot.to_dict())


store = RunStore()

