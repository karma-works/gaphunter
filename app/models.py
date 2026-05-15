from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConstraintSet(BaseModel):
    raw_prompt: str
    geography: str | None = None
    industry: str | None = None
    exclusions: list[str] = Field(default_factory=list)
    complexity_threshold: str = "medium"
    io_type: str = "digital"


class Evidence(BaseModel):
    label: str
    url: HttpUrl
    note: str


class SearchResult(BaseModel):
    title: str
    snippet: str
    url: HttpUrl


class ProgressEvent(BaseModel):
    id: str
    sequence: int
    stage: str
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceEvidence(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    url: HttpUrl
    title: str | None = None
    snippet: str | None = None
    provider: str | None = None
    query: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobCandidate(BaseModel):
    title: str
    description: str
    industry: str | None = None
    source_url: HttpUrl
    estimated_salary_band: str | None = None
    io_type: str = "digital"
    complexity_signal: str = "medium"


class CompetitorCheckResult(BaseModel):
    job_title: str
    competitors_found: list[SearchResult] = Field(default_factory=list)
    gap_confirmed: bool
    coverage_note: str


class Critique(BaseModel):
    objections: list[str]
    severity: str


class IdeaBrief(BaseModel):
    title: str
    one_liner: str
    target_customer: str
    job_being_replaced: str
    gap_evidence: list[Evidence]
    source_urls: list[HttpUrl]
    ai_feasibility_note: str
    critique: Critique
    research_coverage_score: float = Field(ge=0, le=1)
    score_rationale: str


class RunRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class RunResult(BaseModel):
    schema_version: int = 1
    id: str = Field(default_factory=lambda: uuid4().hex)
    status: RunStatus = RunStatus.COMPLETED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    constraints: ConstraintSet
    ideas: list[IdeaBrief]
    run_duration_s: float
    mode: str

    def firestore_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class RunStatusResponse(BaseModel):
    schema_version: int = 1
    id: str
    run_id: str
    status: RunStatus
    created_at: datetime
    constraints: ConstraintSet | None = None
    ideas: list[IdeaBrief] | None = None
    events: list[ProgressEvent] = Field(default_factory=list)
    progress: str | None = None
    error: str | None = None
    run_duration_s: float | None = None
    mode: str | None = None

    @classmethod
    def from_result(
        cls,
        result: RunResult,
        *,
        events: list[ProgressEvent] | None = None,
        progress: str | None = None,
    ) -> "RunStatusResponse":
        return cls(
            schema_version=result.schema_version,
            id=result.id,
            run_id=result.id,
            status=result.status,
            created_at=result.created_at,
            constraints=result.constraints,
            ideas=result.ideas,
            events=events or [],
            progress=progress,
            run_duration_s=result.run_duration_s,
            mode=result.mode,
        )

    def firestore_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
