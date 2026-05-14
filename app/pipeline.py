from __future__ import annotations

import re
import time
from datetime import UTC, datetime

from app.models import (
    CompetitorCheckResult,
    ConstraintSet,
    Critique,
    Evidence,
    IdeaBrief,
    JobCandidate,
    RunRequest,
    RunResult,
    SearchResult,
)
from app.search import SearchError, competitor_search, job_search
from app.settings import settings


GEOGRAPHY_HINTS = {
    "switzerland": "Switzerland",
    "swiss": "Switzerland",
    "dach": "DACH",
    "germany": "Germany",
    "austria": "Austria",
    "europe": "Europe",
    "us": "United States",
    "usa": "United States",
}

INDUSTRY_HINTS = {
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


def parse_constraints(prompt: str) -> ConstraintSet:
    normalized = prompt.lower()
    geography = next((value for key, value in GEOGRAPHY_HINTS.items() if key in normalized), None)
    industry = next((value for key, value in INDUSTRY_HINTS.items() if key in normalized), None)
    exclusions = re.findall(r"exclude\s+([a-z0-9 ,/-]+)", normalized)

    if "high" in normalized or "complex" in normalized:
        complexity = "high"
    elif "low" in normalized or "simple" in normalized:
        complexity = "low"
    else:
        complexity = "medium"

    io_type = "digital" if "digital" in normalized or "software" in normalized else "mixed"

    return ConstraintSet(
        raw_prompt=prompt,
        geography=geography,
        industry=industry,
        exclusions=[item.strip() for group in exclusions for item in group.split(",") if item.strip()],
        complexity_threshold=complexity,
        io_type=io_type,
    )


def generate_demo_ideas(constraints: ConstraintSet) -> list[IdeaBrief]:
    geography = constraints.geography or "the target market"
    industry = constraints.industry or "B2B services"
    evidence_url = "https://www.bls.gov/ooh/business-and-financial/home.htm"

    ideas = [
        IdeaBrief(
            title="Compliance Intake Analyst Agent",
            one_liner=(
                "Turns messy customer documents and email trails into structured compliance "
                "review packets for specialist teams."
            ),
            target_customer=f"Regulated {industry.lower()} operators in {geography}",
            job_being_replaced="Junior compliance analyst intake and first-pass review",
            gap_evidence=[
                Evidence(
                    label="Role category signal",
                    url=evidence_url,
                    note="Public occupational data shows persistent demand for business and financial operations roles.",
                )
            ],
            source_urls=[evidence_url],
            ai_feasibility_note=(
                "The workflow is mostly text extraction, classification, checklist completion, "
                "and exception routing, which fits a human-in-the-loop agent."
            ),
            critique=Critique(
                objections=[
                    "A credible product needs jurisdiction-specific rule packs before buyers trust automation.",
                    "Large incumbents may already bundle intake automation into compliance suites.",
                ],
                severity="medium",
            ),
            research_coverage_score=0.62,
            score_rationale="Demo-mode score: source-backed role demand is present, but live competitor search is not configured.",
        ),
        IdeaBrief(
            title="RFP Qualification Agent",
            one_liner=(
                "Reads inbound tenders, extracts fit criteria, flags deal-breakers, and drafts a bid/no-bid memo."
            ),
            target_customer=f"SMB and mid-market sales teams serving {geography}",
            job_being_replaced="Sales operations coordinator doing tender triage",
            gap_evidence=[
                Evidence(
                    label="Role category signal",
                    url=evidence_url,
                    note="Operations roles with repetitive document review are a strong fit for constrained AI assistance.",
                )
            ],
            source_urls=[evidence_url],
            ai_feasibility_note=(
                "The task has defined inputs, repeatable scoring rubrics, and clear escalation paths."
            ),
            critique=Critique(
                objections=[
                    "Tender formats vary by buyer and market, so onboarding may require custom extraction templates.",
                    "The buyer may see this as a feature inside CRM or proposal software rather than a standalone product.",
                ],
                severity="medium",
            ),
            research_coverage_score=0.58,
            score_rationale="Demo-mode score: plausible digital workflow, but live job-board and competitor coverage are pending.",
        ),
    ]

    excluded_terms = {term.lower() for term in constraints.exclusions}
    if not excluded_terms:
        return ideas

    return [
        idea
        for idea in ideas
        if not any(term in idea.title.lower() or term in idea.one_liner.lower() for term in excluded_terms)
    ]


def build_job_query(constraints: ConstraintSet) -> str:
    parts = [
        constraints.geography or "",
        constraints.industry or "B2B",
        "complex digital operations job posting",
    ]
    if constraints.complexity_threshold == "high":
        parts.append("senior specialist analyst")
    return " ".join(part for part in parts if part).strip()


def build_competitor_query(candidate: JobCandidate) -> str:
    return f"AI agent for {candidate.title}"


def results_to_job_candidates(
    results: list[SearchResult], constraints: ConstraintSet
) -> list[JobCandidate]:
    candidates: list[JobCandidate] = []
    for result in results:
        if not result.url:
            continue
        candidates.append(
            JobCandidate(
                title=result.title[:120],
                description=result.snippet or result.title,
                industry=constraints.industry,
                source_url=result.url,
                io_type=constraints.io_type,
                complexity_signal=constraints.complexity_threshold,
            )
        )
    return candidates


def check_competitors(candidate: JobCandidate) -> CompetitorCheckResult:
    checked_at = datetime.now(UTC).date().isoformat()
    competitors = competitor_search(build_competitor_query(candidate), limit=3)
    return CompetitorCheckResult(
        job_title=candidate.title,
        competitors_found=competitors,
        gap_confirmed=not competitors,
        coverage_note=(
            "Checked configured competitor Programmable Search Engine via Google Custom "
            f"Search as of {checked_at}. Non-indexed and stealth products not covered."
        ),
    )


def synthesize_live_ideas(
    candidates: list[JobCandidate], competitor_checks: list[CompetitorCheckResult]
) -> list[IdeaBrief]:
    ideas: list[IdeaBrief] = []
    checks_by_title = {check.job_title: check for check in competitor_checks}

    for candidate in candidates[:3]:
        check = checks_by_title.get(candidate.title)
        competitor_count = len(check.competitors_found) if check else 0
        coverage_note = check.coverage_note if check else "Competitor coverage was not completed."
        score = 0.72 if competitor_count == 0 else max(0.35, 0.68 - (competitor_count * 0.1))
        source_urls = [candidate.source_url]
        if check:
            source_urls.extend(result.url for result in check.competitors_found)

        ideas.append(
            IdeaBrief(
                title=f"{candidate.title} Agent",
                one_liner=(
                    "Automates first-pass intake, classification, and exception routing for "
                    f"work similar to: {candidate.description[:140]}"
                ),
                target_customer=candidate.industry or "B2B teams with document-heavy operations",
                job_being_replaced=candidate.title,
                gap_evidence=[
                    Evidence(
                        label="Job-market source",
                        url=candidate.source_url,
                        note=candidate.description[:240],
                    )
                ],
                source_urls=source_urls,
                ai_feasibility_note=(
                    "This is a candidate because the source describes repeatable knowledge-work "
                    "inputs that can be parsed, classified, summarized, and escalated."
                ),
                critique=Critique(
                    objections=[
                        "The current implementation has search evidence but not yet LLM-grounded extraction.",
                        (
                            "Competitor coverage depends on the configured Programmable Search "
                            "Engine and may miss non-indexed products."
                        ),
                    ],
                    severity="medium" if competitor_count else "low",
                ),
                research_coverage_score=round(score, 2),
                score_rationale=(
                    f"Live-search score based on one job source and {competitor_count} "
                    f"competitor results. {coverage_note}"
                ),
            )
        )
    return ideas


def generate_live_search_ideas(constraints: ConstraintSet) -> list[IdeaBrief]:
    job_results = job_search(build_job_query(constraints), limit=5)
    candidates = results_to_job_candidates(job_results, constraints)
    if not candidates:
        return []
    competitor_checks = [check_competitors(candidate) for candidate in candidates[:3]]
    return synthesize_live_ideas(candidates, competitor_checks)


def run_pipeline(request: RunRequest) -> RunResult:
    start = time.perf_counter()
    constraints = parse_constraints(request.prompt)
    mode = "live_search" if settings.live_research_enabled else "demo"

    try:
        ideas = (
            generate_live_search_ideas(constraints)
            if settings.live_research_enabled
            else generate_demo_ideas(constraints)
        )
    except SearchError:
        mode = "demo"
        ideas = generate_demo_ideas(constraints)

    if not ideas:
        mode = "demo"
        ideas = generate_demo_ideas(constraints)

    return RunResult(
        constraints=constraints,
        ideas=ideas,
        run_duration_s=round(time.perf_counter() - start, 4),
        mode=mode,
    )
