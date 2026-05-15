from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_deterministic_result_dict(
    prompt: str,
    *,
    run_id: str | None = None,
    started_at: float | None = None,
) -> dict[str, Any]:
    start = started_at if started_at is not None else time.perf_counter()
    result_id = run_id or uuid4().hex
    evidence_url = "https://example.com/gaphunter-agent-engine-spike"

    return {
        "schema_version": 1,
        "id": result_id,
        "run_id": result_id,
        "status": "completed",
        "created_at": _now_iso(),
        "constraints": {
            "raw_prompt": prompt,
            "geography": None,
            "industry": None,
            "exclusions": [],
            "complexity_threshold": "medium",
            "io_type": "digital",
        },
        "ideas": [
            {
                "title": "Agent Engine Spike Brief",
                "one_liner": "Verifies Agent Engine can write a schema-valid GapHunter run result.",
                "target_customer": "GapHunter engineering",
                "job_being_replaced": "Manual deployment smoke testing",
                "gap_evidence": [
                    {
                        "label": "Deterministic spike evidence",
                        "url": evidence_url,
                        "note": "Static source used only to validate Agent Engine Firestore writes.",
                    }
                ],
                "source_urls": [evidence_url],
                "ai_feasibility_note": (
                    "This deterministic result does not call an LLM; it validates orchestration, "
                    "schema compatibility, and Firestore writes."
                ),
                "critique": {
                    "objections": [
                        "This spike does not validate Gemini or Brave Search integration.",
                        "This spike only proves the deployment and persistence path.",
                    ],
                    "severity": "low",
                },
                "research_coverage_score": 0.1,
                "score_rationale": "Spike score: validates plumbing only, not research quality.",
            }
        ],
        "run_duration_s": round(time.perf_counter() - start, 4),
        "mode": "agent_engine_spike",
        "progress": "completed",
    }


def build_deterministic_result(prompt: str, *, started_at: float | None = None):
    from app.models import RunResult

    return RunResult.model_validate(
        build_deterministic_result_dict(prompt, started_at=started_at)
    )


class GapHunterAgent:
    def __init__(self, store=None, *, project_id: str | None = None) -> None:
        self._store = store
        self._project_id = project_id

    def hello(self, name: str = "world") -> dict[str, str]:
        return {"message": f"hello {name}"}

    def query(self, **kwargs) -> dict[str, str]:
        run_id = kwargs.get("run_id")
        prompt = kwargs.get("prompt")
        if run_id and prompt:
            return self.run(run_id=run_id, prompt=prompt, user_id=kwargs.get("user_id"))
        return self.hello(kwargs.get("name", "world"))

    def run(self, run_id: str, prompt: str, user_id: str | None = None) -> dict[str, str]:
        started_at = time.perf_counter()

        if self._store is not None:
            return self._run_with_local_store(run_id, prompt, user_id, started_at)

        return self._run_with_firestore(run_id, prompt, user_id, started_at)

    def _run_with_local_store(
        self,
        run_id: str,
        prompt: str,
        user_id: str | None,
        started_at: float,
    ) -> dict[str, str]:
        try:
            self._store.mark_running(run_id)
            self._store.append_event(
                run_id,
                "running",
                f"Agent Engine spike started for {user_id or 'anonymous user'}.",
            )
            result = build_deterministic_result(prompt, started_at=started_at)
            status = self._store.complete_with_result(run_id, result)
            return {"run_id": status.run_id, "status": status.status.value}
        except Exception as exc:
            status = self._store.fail_with_error(run_id, str(exc))
            return {"run_id": status.run_id, "status": status.status.value}

    def _run_with_firestore(
        self,
        run_id: str,
        prompt: str,
        user_id: str | None,
        started_at: float,
    ) -> dict[str, str]:
        from google.cloud import firestore

        project_id = self._project_id or os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        client = firestore.Client(project=project_id)
        run_ref = client.collection(os.getenv("FIRESTORE_COLLECTION", "runs")).document(run_id)

        try:
            run_ref.update({"status": "running", "progress": "running"})
            event = {
                "id": "000001",
                "sequence": 1,
                "stage": "running",
                "message": f"Agent Engine spike started for {user_id or 'anonymous user'}.",
                "created_at": _now_iso(),
            }
            run_ref.collection("events").document(event["id"]).set(event)
            run_ref.update({"event_sequence": 1})

            result = build_deterministic_result_dict(prompt, run_id=run_id, started_at=started_at)
            run_ref.update(result)
            return {"run_id": run_id, "status": "completed"}
        except Exception as exc:
            run_ref.update({"status": "failed", "progress": "failed", "error": str(exc)[:500]})
            return {"run_id": run_id, "status": "failed"}


root_agent = GapHunterAgent()
