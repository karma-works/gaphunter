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
