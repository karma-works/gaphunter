from __future__ import annotations

import logging
import threading
from typing import Callable, Protocol

from app.models import RunRequest, RunResult
from app.pipeline import run_pipeline
from app.storage import RunStore

logger = logging.getLogger(__name__)


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


class AgentEngineGateway:
    def __init__(
        self,
        resource_name: str,
        store: RunStore,
        *,
        max_search_queries: int = 20,
        max_gemini_calls: int = 50,
    ) -> None:
        self._resource_name = resource_name
        self._store = store
        self._max_search_queries = max_search_queries
        self._max_gemini_calls = max_gemini_calls

    def start_run(self, run_id: str, request: RunRequest) -> None:
        thread = threading.Thread(
            target=self._invoke,
            args=(run_id, request),
            daemon=True,
            name=f"agent-engine-{run_id[:8]}",
        )
        thread.start()

    def _invoke(self, run_id: str, request: RunRequest) -> None:
        try:
            from vertexai import agent_engines

            remote_agent = agent_engines.get(self._resource_name)
            remote_agent.query(
                run_id=run_id,
                prompt=request.prompt,
                max_search_queries=self._max_search_queries,
                max_gemini_calls=self._max_gemini_calls,
            )
        except Exception as exc:
            logger.exception("AgentEngineGateway invocation failed for run %s", run_id)
            try:
                self._store.fail_with_error(
                    run_id, f"Agent Engine invocation failed: {exc}"[:500]
                )
            except Exception:
                logger.exception("Failed to write error state for run %s", run_id)


def build_agent_gateway(backend: str, store: RunStore) -> AgentGateway:
    if backend == "local":
        return LocalPipelineAgentGateway(store)
    if backend == "fake":
        return FakeAgentGateway(store)
    if backend == "agent_engine":
        from app.settings import settings

        resource_name = settings.agent_engine_resource_name
        if not resource_name:
            raise ValueError(
                "AGENT_ENGINE_RESOURCE_NAME must be set when AGENT_BACKEND=agent_engine"
            )
        return AgentEngineGateway(
            resource_name,
            store,
            max_search_queries=settings.max_search_queries_per_run,
            max_gemini_calls=settings.max_gemini_calls_per_run,
        )
    raise ValueError(f"Unsupported AGENT_BACKEND: {backend}")
