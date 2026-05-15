from __future__ import annotations

from pydantic import BaseModel, Field


class _ConstraintOutput(BaseModel):
    geography: str | None = None
    industry: str | None = None
    exclusions: list[str] = Field(default_factory=list)
    complexity_threshold: str = "medium"
    io_type: str = "digital"


_SYSTEM_PROMPT = """
Extract structured constraints from this market research prompt.

Rules:
- geography: country or region explicitly mentioned (e.g. "Switzerland", "DACH", "Europe"), or null if none
- industry: specific industry mentioned (e.g. "Healthcare", "Financial services"), or null if none
- exclusions: list of categories the user explicitly says to exclude (e.g. ["fintech", "tax"])
- complexity_threshold: "low", "medium", or "high" based on complexity language in the prompt
- io_type: "digital" if digital inputs/outputs are mentioned, "mixed" otherwise
""".strip()


def parse_constraints_with_gemini(prompt: str, api_key: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
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
