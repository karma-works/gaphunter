from __future__ import annotations

from typing import Callable, Protocol

from app.models import RunRequest, RunResult
from app.pipeline import run_pipeline
from app.storage import RunStore


class AgentGateway(Protocol):
    def start_run(self, run_id: str, request: RunRequest) -> None:
        pass


class LocalPipelineAgentGateway:
    def __init__(
        self,
        store: RunStore,
        pipeline: Callable[[RunRequest], RunResult] = run_pipeline,
    ) -> None:
        self._store = store
        self._pipeline = pipeline

    def start_run(self, run_id: str, request: RunRequest) -> None:
        try:
            self._store.mark_running(run_id)
            self._store.append_event(run_id, "running", "Research pipeline started.")
            result = self._pipeline(request)
            self._store.complete_with_result(run_id, result)
        except Exception as exc:
            self._store.fail_with_error(run_id, str(exc))


class FakeAgentGateway:
    def __init__(
        self,
        store: RunStore,
        *,
        result: RunResult | None = None,
        error: str | None = None,
    ) -> None:
        self._store = store
        self._result = result
        self._error = error

    def start_run(self, run_id: str, request: RunRequest) -> None:
        try:
            self._store.mark_running(run_id)
            self._store.append_event(run_id, "running", "Fake agent started.")
            if self._error:
                raise RuntimeError(self._error)
            result = self._result or run_pipeline(request)
            self._store.complete_with_result(run_id, result)
        except Exception as exc:
            self._store.fail_with_error(run_id, str(exc))


def build_agent_gateway(backend: str, store: RunStore) -> AgentGateway:
    if backend == "local":
        return LocalPipelineAgentGateway(store)
    if backend == "fake":
        return FakeAgentGateway(store)
    if backend == "agent_engine":
        raise NotImplementedError("AGENT_BACKEND=agent_engine is planned for Phase 5.")
    raise ValueError(f"Unsupported AGENT_BACKEND: {backend}")
