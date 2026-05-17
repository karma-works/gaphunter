from __future__ import annotations

from pydantic import BaseModel, Field

GEMINI_MODEL = "gemini-3-flash-preview"


class _ConstraintOutput(BaseModel):
    geography: str | None = None
    industry: str | None = None
    exclusions: list[str] = Field(default_factory=list)
    complexity_threshold: str = "medium"
    io_type: str = "digital"


class _CompetitorOutput(BaseModel):
    title: str
    url: str
    reason: str = ""


class _CompetitorAnalysisOutput(BaseModel):
    competitors_found: list[_CompetitorOutput] = Field(default_factory=list)
    gap_confirmed: bool
    coverage_note: str


class _IdeaOutput(BaseModel):
    job_title: str
    title: str
    one_liner: str
    target_customer: str
    ai_feasibility_note: str
    critique_objections: list[str] = Field(default_factory=list)
    critique_severity: str = "medium"


class _IdeaSynthesisOutput(BaseModel):
    ideas: list[_IdeaOutput] = Field(default_factory=list)


class _CritiqueOutput(BaseModel):
    job_title: str
    objections: list[str] = Field(default_factory=list)
    severity: str = "medium"
    research_coverage_score: float = 0.5
    score_rationale: str = ""


class _CritiqueAndScoringOutput(BaseModel):
    critiques: list[_CritiqueOutput] = Field(default_factory=list)


_SYSTEM_PROMPT = """
Extract structured constraints from this market research prompt.

Rules:
- geography: country or region explicitly mentioned (e.g. "Switzerland", "DACH", "Europe"), or null if none
- industry: specific industry mentioned (e.g. "Healthcare", "Financial services"), or null if none
- exclusions: list of categories the user explicitly says to exclude (e.g. ["fintech", "tax"])
- complexity_threshold: "low", "medium", or "high" based on complexity language in the prompt
- io_type: "digital" if digital inputs/outputs are mentioned, "mixed" otherwise
""".strip()


_COMPETITOR_PROMPT = """
Analyze whether the search results are direct competitors for an AI-agent product
that would automate the candidate job.

Rules:
- Only return competitors whose URL is present in the provided search results.
- Treat broad articles, job posts, directories, and unrelated SaaS as non-competitors.
- If evidence is weak, omit the result and explain the coverage limit.
- coverage_note must mention that only public indexed web results were checked.
""".strip()


_IDEA_PROMPT = """
Create concise startup idea briefs from job candidates and competitor checks.

Rules:
- Return one idea per candidate at most.
- job_title must exactly match a provided candidate title.
- Ground the brief in the provided job description and competitor check.
- Do not invent source URLs, customers, competitors, or scores.
- Critique objections must be specific to source coverage, competitors, buyer risk,
  workflow adoption, or feasibility.
""".strip()


_CRITIQUE_PROMPT = """
Review each idea brief and produce data-grounded objections and a research coverage score.

Rules for objections:
- Write 2-4 objections per idea.
- Every objection must cite specific evidence from the provided sources: the job description text,
  competitor URLs found, coverage gaps stated in coverage_note, or missing source types.
- Do NOT write generic objections like "market size is unknown" or "competition may exist" without
  grounding them in the actual evidence provided.
- Good: "The job source is a single posting from one mid-size firm at [URL] — role may be too
  niche for a horizontal product without confirming demand across multiple employers."
- Good: "Competitor check found [Tool] at [URL] describing overlapping automation — differentiation
  requires direct feature comparison before assuming a gap."
- Bad: "Market adoption risk is present." (no evidence anchor)
- Bad: "Competition may exist that was not found." (just restating the coverage note)
- severity: "low" if gap is clearly confirmed and evidence is rich; "medium" if mixed;
  "high" if strong competitors found or evidence is thin.

Rules for research_coverage_score (0.0–1.0, reflects evidence depth, NOT business viability):
- Score what was researched, not whether the idea will succeed.
- 0.8–1.0: multiple distinct job sources, no competitors found, rich job descriptions.
- 0.6–0.8: one solid job source, gap confirmed, competitor check was substantive.
- 0.4–0.6: one job source with competitors found (gap unconfirmed), or thin job description.
- 0.2–0.4: sparse evidence, many competitors, or formulaic/short job descriptions.
- 0.0–0.2: no substantive source evidence.
- score_rationale must name the specific source URLs used, how many competitor results were
  returned, and what research gaps remain. Example format:
  "Primary job evidence: [URL]. Competitor check returned N results ([URL1], [URL2]).
   Coverage limited to public indexed web; niche/stealth tools not checked."
""".strip()


def parse_constraints_with_gemini(prompt: str, api_key: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"{_SYSTEM_PROMPT}\n\nPrompt: {prompt}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_ConstraintOutput,
        ),
    )
    parsed = _ConstraintOutput.model_validate_json(response.text)
    return {
        "raw_prompt": prompt,
        "geography": parsed.geography,
        "industry": parsed.industry,
        "exclusions": parsed.exclusions,
        "complexity_threshold": parsed.complexity_threshold,
        "io_type": parsed.io_type,
    }


def analyze_competitors_with_gemini(
    candidate: dict,
    search_results: list[dict],
    api_key: str,
) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            f"{_COMPETITOR_PROMPT}\n\n"
            f"Candidate:\n{candidate}\n\n"
            f"Search results:\n{search_results}"
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_CompetitorAnalysisOutput,
        ),
    )
    parsed = _CompetitorAnalysisOutput.model_validate_json(response.text)
    return parsed.model_dump()


def synthesize_ideas_with_gemini(
    constraints: dict,
    candidates: list[dict],
    competitor_checks: list[dict],
    api_key: str,
) -> list[dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            f"{_IDEA_PROMPT}\n\n"
            f"Constraints:\n{constraints}\n\n"
            f"Candidates:\n{candidates}\n\n"
            f"Competitor checks:\n{competitor_checks}"
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_IdeaSynthesisOutput,
        ),
    )
    parsed = _IdeaSynthesisOutput.model_validate_json(response.text)
    return [idea.model_dump() for idea in parsed.ideas]


def critique_and_score_with_gemini(
    ideas: list[dict],
    candidates: list[dict],
    competitor_checks: list[dict],
    api_key: str,
) -> list[dict]:
    """
    Call Gemini to produce data-grounded critique and research coverage scores.

    Returns a list of raw critique dicts, one per idea, each containing:
    job_title, objections, severity, research_coverage_score, score_rationale.
    Matching these back to idea briefs is the caller's responsibility.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            f"{_CRITIQUE_PROMPT}\n\n"
            f"Ideas:\n{ideas}\n\n"
            f"Candidates:\n{candidates}\n\n"
            f"Competitor checks:\n{competitor_checks}"
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_CritiqueAndScoringOutput,
        ),
    )
    parsed = _CritiqueAndScoringOutput.model_validate_json(response.text)
    return [c.model_dump() for c in parsed.critiques]
