from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

_MAX_CANDIDATES = 3

_GEOGRAPHY_HINTS = {
    "switzerland": "Switzerland",
    "swiss": "Switzerland",
    "dach": "DACH",
    "germany": "Germany",
    "austria": "Austria",
    "europe": "Europe",
    "us": "United States",
    "usa": "United States",
}

_INDUSTRY_HINTS = {
    "fintech": "Financial services",
    "finance": "Financial services",
    "health": "Healthcare",
    "insurance": "Insurance",
    "legal": "Legal services",
    "logistics": "Logistics",
    "construction": "Construction",
    "manufacturing": "Manufacturing",
    "real estate": "Real estate",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Run budget — kill switch for search and Gemini calls
# ---------------------------------------------------------------------------

@dataclass
class _RunBudget:
    max_search_queries: int = 20
    max_gemini_calls: int = 50
    search_queries_used: int = field(default=0, init=False)
    gemini_calls_used: int = field(default=0, init=False)

    def consume_search(self) -> None:
        """Call before each Brave Search query. Raises RuntimeError when budget is exhausted."""
        if self.search_queries_used >= self.max_search_queries:
            raise RuntimeError(
                f"Run aborted: search query budget exhausted ({self.max_search_queries} max)"
            )
        self.search_queries_used += 1

    def consume_gemini(self) -> None:
        """Call before each Gemini API call. Raises RuntimeError when budget is exhausted."""
        if self.gemini_calls_used >= self.max_gemini_calls:
            raise RuntimeError(
                f"Run aborted: Gemini call budget exhausted ({self.max_gemini_calls} max)"
            )
        self.gemini_calls_used += 1


# ---------------------------------------------------------------------------
# Deterministic spike result — used as fallback when no API keys are configured
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pure helper functions — shared between both run paths
# ---------------------------------------------------------------------------

def _regex_parse_constraints(prompt: str) -> dict:
    normalized = prompt.lower()
    geography = next((v for k, v in _GEOGRAPHY_HINTS.items() if k in normalized), None)
    industry = next((v for k, v in _INDUSTRY_HINTS.items() if k in normalized), None)
    exclusions = re.findall(r"exclude\s+([a-z0-9 ,/-]+)", normalized)
    if "high" in normalized or "complex" in normalized:
        complexity = "high"
    elif "low" in normalized or "simple" in normalized:
        complexity = "low"
    else:
        complexity = "medium"
    io_type = "digital" if "digital" in normalized or "software" in normalized else "mixed"
    return {
        "raw_prompt": prompt,
        "geography": geography,
        "industry": industry,
        "exclusions": [
            item.strip()
            for group in exclusions
            for item in group.split(",")
            if item.strip()
        ],
        "complexity_threshold": complexity,
        "io_type": io_type,
    }


def _build_job_query(constraints: dict) -> str:
    parts = [
        constraints.get("geography") or "",
        constraints.get("industry") or "B2B",
        "complex digital operations job posting role responsibilities",
    ]
    if constraints.get("complexity_threshold") == "high":
        parts.append("senior specialist analyst")
    return " ".join(p for p in parts if p).strip()


def _build_competitor_query(candidate: dict) -> str:
    return f"AI agent software for {candidate['title']}"


def _results_to_candidates(results: list[dict], constraints: dict) -> list[dict]:
    """Maps search results to job candidate dicts. Drops any result without a URL."""
    candidates = []
    for result in results:
        url = result.get("url")
        if not url:
            continue
        candidates.append({
            "title": result["title"][:120],
            "description": (result.get("snippet") or result["title"])[:300],
            "industry": constraints.get("industry"),
            "source_url": url,
            "io_type": constraints.get("io_type", "digital"),
            "complexity_signal": constraints.get("complexity_threshold", "medium"),
            "query": result.get("query"),
        })
    return candidates


def _build_competitor_check(candidate: dict, results: list[dict]) -> dict:
    competitors = [
        {
            "title": result["title"],
            "url": result["url"],
            "snippet": result.get("snippet", ""),
            "query": result.get("query"),
        }
        for result in results
        if result.get("url") and result.get("title")
    ]
    checked_at = datetime.now(timezone.utc).date().isoformat()
    return {
        "job_title": candidate["title"],
        "competitors_found": competitors,
        "gap_confirmed": not competitors,
        "coverage_note": (
            f"Checked public web results via Brave Search as of {checked_at}. "
            "Non-indexed, private, and stealth products are not covered."
        ),
    }


def _candidates_to_ideas_and_sources(
    candidates: list[dict],
    competitor_checks: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Phase 6a synthesis: maps job candidates to IdeaBriefs without competitor checks.
    Phase 6b will add competitor analysis and LLM-grounded synthesis.
    """
    ideas = []
    sources = []
    checks_by_title = {
        check["job_title"]: check
        for check in (competitor_checks or [])
    }
    for candidate in candidates[:_MAX_CANDIDATES]:
        url = candidate["source_url"]
        check = checks_by_title.get(candidate["title"], {})
        competitors = check.get("competitors_found", [])
        gap_confirmed = bool(check.get("gap_confirmed", False))
        source_urls = [url] + [competitor["url"] for competitor in competitors]
        sources.append({
            "url": url,
            "title": candidate["title"],
            "snippet": candidate["description"],
            "provider": "brave",
            "query": candidate.get("query"),
        })
        for competitor in competitors:
            sources.append({
                "url": competitor["url"],
                "title": competitor["title"],
                "snippet": competitor.get("snippet", ""),
                "provider": "brave",
                "query": competitor.get("query"),
            })
        competitor_note = (
            "No direct AI-agent competitors found in public search results."
            if gap_confirmed
            else (
                f"Found {len(competitors)} possible existing competitor"
                f"{'' if len(competitors) == 1 else 's'}."
            )
        )
        ideas.append({
            "title": f"{candidate['title']} Agent",
            "one_liner": (
                "Automates first-pass intake, classification, and exception routing for "
                f"work similar to: {candidate['description'][:140]}"
            ),
            "target_customer": (
                candidate.get("industry") or "B2B teams with document-heavy operations"
            ),
            "job_being_replaced": candidate["title"],
            "gap_confirmed": gap_confirmed,
            "gap_evidence": [
                {
                    "label": "Job-market source",
                    "url": url,
                    "note": candidate["description"][:240],
                },
                {
                    "label": "Competitor coverage",
                    "url": source_urls[-1],
                    "note": f"{competitor_note} {check.get('coverage_note', '')}".strip(),
                }
            ],
            "source_urls": source_urls,
            "ai_feasibility_note": (
                "Candidate identified because the source describes repeatable knowledge-work "
                "inputs suitable for AI-assisted processing."
            ),
            "critique": {
                "objections": [
                    (
                        "Competitor coverage found possible existing tools; differentiation "
                        "needs manual validation."
                        if competitors else
                        "Public competitor search found no direct tools, but non-indexed "
                        "products may still exist."
                    ),
                    "Market size and buyer WTP require validation beyond job-board signals.",
                ],
                "severity": "medium",
            },
            "research_coverage_score": 0.68 if gap_confirmed else max(0.35, 0.62 - len(competitors) * 0.08),
            "score_rationale": (
                f"Phase 6b score: one job-market source and {len(competitors)} "
                f"competitor-search result{'' if len(competitors) == 1 else 's'}. "
                f"{check.get('coverage_note', '')}"
            ),
        })
    return ideas, sources


def _build_result_dict(
    run_id: str,
    constraints: dict,
    ideas: list[dict],
    started_at: float,
    *,
    mode: str = "live_search",
) -> dict:
    return {
        "schema_version": 1,
        "id": run_id,
        "run_id": run_id,
        "status": "completed",
        "created_at": _now_iso(),
        "constraints": constraints,
        "ideas": ideas,
        "run_duration_s": round(time.perf_counter() - started_at, 4),
        "mode": mode,
        "progress": "completed",
    }


# ---------------------------------------------------------------------------
# GapHunterAgent — deployed to Vertex AI Agent Engine
# ---------------------------------------------------------------------------

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
            return self.run(
                run_id=run_id,
                prompt=prompt,
                user_id=kwargs.get("user_id"),
                max_search_queries=int(kwargs.get("max_search_queries", 20)),
                max_gemini_calls=int(kwargs.get("max_gemini_calls", 50)),
            )
        return self.hello(kwargs.get("name", "world"))

    def run(
        self,
        run_id: str,
        prompt: str,
        user_id: str | None = None,
        *,
        max_search_queries: int = 20,
        max_gemini_calls: int = 50,
    ) -> dict[str, str]:
        started_at = time.perf_counter()
        budget = _RunBudget(max_search_queries=max_search_queries, max_gemini_calls=max_gemini_calls)

        if self._store is not None:
            return self._run_with_local_store(run_id, prompt, user_id, started_at, budget)

        return self._run_with_firestore(run_id, prompt, user_id, started_at, budget)

    # ------------------------------------------------------------------
    # Agent steps — return data, never write to storage
    # ------------------------------------------------------------------

    def _constraint_agent(self, prompt: str, budget: _RunBudget) -> dict:
        """Parse prompt into a ConstraintSet-compatible dict via Gemini, with regex fallback."""
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                budget.consume_gemini()
                from agent.tools.gemini import parse_constraints_with_gemini
                return parse_constraints_with_gemini(prompt, api_key)
            except Exception:
                logger.exception("Gemini constraint parsing failed; falling back to regex")
        return _regex_parse_constraints(prompt)

    def _job_research_agent(
        self, constraints: dict, budget: _RunBudget, brave_key: str
    ) -> list[dict]:
        """Search for jobs. Returns only source-backed candidates (URL required)."""
        budget.consume_search()
        query = _build_job_query(constraints)
        from agent.tools.search import brave_search
        results = brave_search(query, brave_key, limit=5)
        return _results_to_candidates(results, constraints)

    def _competitor_agent(
        self, candidates: list[dict], budget: _RunBudget, brave_key: str
    ) -> list[dict]:
        """Search for existing AI products for each job candidate."""
        from agent.tools.search import brave_search

        checks = []
        for candidate in candidates[:_MAX_CANDIDATES]:
            budget.consume_search()
            query = _build_competitor_query(candidate)
            results = brave_search(query, brave_key, limit=3)
            checks.append(_build_competitor_check(candidate, results))
        return checks

    def _finalizer(
        self,
        candidates: list[dict],
        constraints: dict,
        competitor_checks: list[dict] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Build IdeaBriefs from candidates. Validates every idea has a source URL."""
        ideas, sources = _candidates_to_ideas_and_sources(candidates, competitor_checks)
        for idea in ideas:
            if not idea.get("source_urls"):
                raise RuntimeError(
                    f"Finalizer produced an idea without a source URL: {idea.get('title')}"
                )
        return ideas, sources

    # ------------------------------------------------------------------
    # Run paths — handle storage I/O
    # ------------------------------------------------------------------

    def _run_with_local_store(
        self,
        run_id: str,
        prompt: str,
        user_id: str | None,
        started_at: float,
        budget: _RunBudget,
    ) -> dict[str, str]:
        try:
            self._store.mark_running(run_id)

            brave_key = os.getenv("BRAVE_SEARCH_API_KEY")
            if not brave_key:
                self._store.append_event(
                    run_id, "running",
                    f"Spike started for {user_id or 'anonymous user'} (no search key).",
                )
                result = build_deterministic_result(prompt, started_at=started_at)
                status = self._store.complete_with_result(run_id, result)
                return {"run_id": status.run_id, "status": status.status.value}

            self._store.append_event(run_id, "parsing_constraints", "Parsing constraints...")
            constraints = self._constraint_agent(prompt, budget)

            self._store.append_event(run_id, "researching_jobs", "Searching for job signals...")
            candidates = self._job_research_agent(constraints, budget, brave_key)

            if not candidates:
                raise RuntimeError(
                    "No source-backed job candidates found. "
                    "Try broadening your constraints or check BRAVE_SEARCH_API_KEY."
                )

            self._store.append_event(
                run_id, "checking_competitors", "Checking for existing AI products..."
            )
            competitor_checks = self._competitor_agent(candidates, budget, brave_key)

            self._store.append_event(
                run_id, "synthesizing_ideas",
                f"Building {min(len(candidates), _MAX_CANDIDATES)} idea briefs...",
            )
            ideas, sources = self._finalizer(candidates, constraints, competitor_checks)

            from app.models import SourceEvidence
            for src in sources:
                self._store.append_source(
                    run_id,
                    SourceEvidence(
                        url=src["url"],
                        title=src.get("title"),
                        snippet=src.get("snippet"),
                        provider=src.get("provider"),
                        query=src.get("query"),
                    ),
                )

            result_dict = _build_result_dict(run_id, constraints, ideas, started_at)
            from app.models import RunResult
            result = RunResult.model_validate(result_dict)
            status = self._store.complete_with_result(run_id, result)
            return {"run_id": status.run_id, "status": status.status.value}

        except Exception as exc:
            logger.exception("Run %s failed", run_id)
            status = self._store.fail_with_error(run_id, str(exc))
            return {"run_id": status.run_id, "status": status.status.value}

    def _run_with_firestore(
        self,
        run_id: str,
        prompt: str,
        user_id: str | None,
        started_at: float,
        budget: _RunBudget,
    ) -> dict[str, str]:
        from google.cloud import firestore

        project_id = (
            self._project_id
            or os.getenv("GCP_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
        )
        client = firestore.Client(project=project_id)
        collection = os.getenv("FIRESTORE_COLLECTION", "runs")
        run_ref = client.collection(collection).document(run_id)

        seq = 0

        def emit(stage: str, message: str) -> None:
            nonlocal seq
            seq += 1
            event = {
                "id": f"{seq:06d}",
                "sequence": seq,
                "stage": stage,
                "message": message,
                "created_at": _now_iso(),
            }
            run_ref.collection("events").document(event["id"]).set(event)
            run_ref.update({"event_sequence": seq, "progress": stage})

        try:
            run_ref.update({"status": "running", "progress": "running"})

            brave_key = os.getenv("BRAVE_SEARCH_API_KEY")
            if not brave_key:
                emit("running", f"Spike started for {user_id or 'anonymous user'} (no search key).")
                result_dict = build_deterministic_result_dict(prompt, run_id=run_id, started_at=started_at)
                run_ref.update(result_dict)
                return {"run_id": run_id, "status": "completed"}

            emit("parsing_constraints", "Parsing constraints...")
            constraints = self._constraint_agent(prompt, budget)

            emit("researching_jobs", "Searching for job signals...")
            candidates = self._job_research_agent(constraints, budget, brave_key)

            if not candidates:
                raise RuntimeError(
                    "No source-backed job candidates found. "
                    "Try broadening your constraints or check BRAVE_SEARCH_API_KEY."
                )

            emit("checking_competitors", "Checking for existing AI products...")
            competitor_checks = self._competitor_agent(candidates, budget, brave_key)

            emit(
                "synthesizing_ideas",
                f"Building {min(len(candidates), _MAX_CANDIDATES)} idea briefs...",
            )
            ideas, sources = self._finalizer(candidates, constraints, competitor_checks)

            for src in sources:
                source_doc = {
                    "id": uuid4().hex,
                    "url": src["url"],
                    "title": src.get("title"),
                    "snippet": src.get("snippet"),
                    "provider": src.get("provider"),
                    "query": src.get("query"),
                    "created_at": _now_iso(),
                }
                run_ref.collection("sources").document(source_doc["id"]).set(source_doc)

            result_dict = _build_result_dict(run_id, constraints, ideas, started_at)
            run_ref.update(result_dict)
            return {"run_id": run_id, "status": "completed"}

        except Exception as exc:
            logger.exception("Run %s failed", run_id)
            run_ref.update({"status": "failed", "progress": "failed", "error": str(exc)[:500]})
            return {"run_id": run_id, "status": "failed"}


root_agent = GapHunterAgent()
