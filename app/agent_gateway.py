from __future__ import annotations

import json
import logging
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
        queue: str | None = None,
        service_url: str | None = None,
        tasks_sa: str | None = None,
    ) -> None:
        self._resource_name = resource_name
        self._store = store
        self._max_search_queries = max_search_queries
        self._max_gemini_calls = max_gemini_calls
        self._queue = queue
        self._service_url = service_url
        self._tasks_sa = tasks_sa

    def start_run(self, run_id: str, request: RunRequest) -> None:
        if not self._queue or not self._service_url or not self._tasks_sa:
            raise ValueError(
                "CLOUD_TASKS_QUEUE, CLOUD_RUN_SERVICE_URL, and CLOUD_TASKS_SA must all be set "
                "when AGENT_BACKEND=agent_engine"
            )
        from google.cloud import tasks_v2

        payload = json.dumps({"run_id": run_id, "prompt": request.prompt}).encode()
        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{self._service_url}/internal/tasks/run-agent",
                headers={"Content-Type": "application/json"},
                body=payload,
                oidc_token=tasks_v2.OidcToken(
                    service_account_email=self._tasks_sa,
                    audience=self._service_url,
                ),
            )
        )
        client = tasks_v2.CloudTasksClient()
        client.create_task(parent=self._queue, task=task)
        logger.info("Enqueued Cloud Task for run %s", run_id)

    def _invoke(self, run_id: str, request: RunRequest) -> None:
        try:
            import vertexai
            from vertexai import agent_engines

            # Extract project and location from the resource name so vertexai.init()
            # does not need separate env vars in Cloud Run.
            # Resource format: projects/{project}/locations/{location}/reasoningEngines/{id}
            parts = self._resource_name.split("/")
            project = parts[1] if len(parts) > 1 else None
            location = parts[3] if len(parts) > 3 else "us-central1"
            vertexai.init(project=project, location=location)

            remote_agent = agent_engines.get(self._resource_name)
            remote_agent.query(
                run_id=run_id,
                prompt=request.prompt,
                max_search_queries=self._max_search_queries,
                max_gemini_calls=self._max_gemini_calls,
            )
            # Sync the in-memory store so the next GET doesn't need a Firestore round-trip.
            self._store.get_status(run_id)
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
            queue=settings.cloud_tasks_queue,
            service_url=settings.cloud_run_service_url,
            tasks_sa=settings.cloud_tasks_sa,
        )
    raise ValueError(f"Unsupported AGENT_BACKEND: {backend}")
