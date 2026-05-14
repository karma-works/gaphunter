from __future__ import annotations

import re
import time

from app.models import ConstraintSet, Critique, Evidence, IdeaBrief, RunRequest, RunResult
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


def run_pipeline(request: RunRequest) -> RunResult:
    start = time.perf_counter()
    constraints = parse_constraints(request.prompt)
    mode = "live" if settings.live_research_enabled else "demo"

    # Live integrations use the same model boundary. Demo mode keeps deployment smoke tests cheap.
    ideas = generate_demo_ideas(constraints)

    return RunResult(
        constraints=constraints,
        ideas=ideas,
        run_duration_s=round(time.perf_counter() - start, 4),
        mode=mode,
    )

