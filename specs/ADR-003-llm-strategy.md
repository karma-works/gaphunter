# ADR-003: LLM Strategy — Gemini 2.0 Flash + Gemini 2.5 Pro

**Status:** Decided
**Date:** 2026-05-14

## Context

The pipeline has two distinct types of LLM work:
1. **High-volume, low-reasoning**: parsing search results, extracting job descriptions, classifying whether a job matches constraints (done 15–30x per run)
2. **Low-volume, high-reasoning**: synthesizing ideas from research, generating adversarial critique, scoring and ranking

Using the same model for both is wasteful (expensive model on cheap tasks) or produces poor output (cheap model on hard tasks).

## Decision

Use Gemini 2.0 Flash for all research/extraction steps. Use Gemini 2.5 Pro for synthesis, adversarial critique, and final scoring.

## Rationale

- Flash is fast (sub-second responses) and cheap. Suitable for the iterative search-and-extract loop where volume is high and reasoning depth is low.
- Pro (2.5) has materially stronger reasoning. The critique layer is the differentiating feature of the product — using a weaker model here produces generic, useless objections and destroys the value proposition.
- Both models are available through the same Gemini API — no extra infrastructure, just a model name parameter change.
- The two-model split is a clean architectural boundary: research pipeline = Flash, synthesis pipeline = Pro.

## What This Option Does NOT Do Well

- Two models means two pricing tiers to track and two sets of rate limits to manage.
- If Gemini 2.5 Pro is deprecated or repriced, the synthesis pipeline needs to migrate. Pin to model version strings, not "latest."
- Flash may hallucinate more on extraction tasks than Pro. Mitigate with strict output schemas (structured JSON responses with explicit fields).

## Consequences

- All LLM calls must specify the model explicitly. No implicit "default model" anywhere in the pipeline.
- Research pipeline prompts must be designed for Flash: short, structured, with JSON output format enforced.
- Critique pipeline prompts must be designed for Pro: longer context, chain-of-thought encouraged, grounded in specific research data.
- Cost per run budget: ~$0.05 Flash (research loops) + ~$0.10 Pro (synthesis + critique) + ~$0.15 search API = ~$0.30 total. Adjust pricing model accordingly.
