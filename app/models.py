from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


class RunStatus(StrEnum):
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


class RunResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    status: RunStatus = RunStatus.COMPLETED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    constraints: ConstraintSet
    ideas: list[IdeaBrief]
    run_duration_s: float
    mode: str

    def firestore_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
