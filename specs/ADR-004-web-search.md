# ADR-004: Web Search — Google Custom Search API (Programmable Search Engine)

**Status:** Decided
**Date:** 2026-05-14

## Context

The agent needs to search the web for two distinct purposes:
1. **Job research**: Find real job postings and role descriptions matching user constraints (e.g., "complex digital-I/O professional roles in Switzerland")
2. **Competitor check**: Determine whether an AI agent product already exists for a specific job type

Both require real-time web data — training data cutoffs make this unusable from the base LLM alone.

Alternatives: Google Custom Search API, SerpAPI (third-party Google wrapper), Bing Search API, Brave Search API, Playwright/browser automation, direct LinkedIn API.

## Decision

Use Google Custom Search API (Programmable Search Engine) with separate search engine configurations for job research and competitor checking.

## Rationale

- Google-native, consistent with the overall stack.
- Programmable Search Engines (PSE) can be scoped to specific domains — job PSE targets LinkedIn, Indeed, jobs.ch, local boards; competitor PSE targets Product Hunt, G2, Crunchbase, app directories.
- Domain-scoped searches produce more relevant results than open-web searches and reduce noise.
- Pricing: 100 free queries/day; $5/1,000 after. A run uses 15–30 queries — cost per run is $0.075–$0.15. Acceptable.
- No third-party dependency (vs. SerpAPI, which is a paid wrapper around Google results).

Playwright/browser automation was rejected: adds significant operational complexity (headless Chrome, anti-bot handling, maintenance), makes Cloud Run deployment harder, and is not needed for v1.

LinkedIn direct API was rejected: extremely restricted for job search use cases, requires partner status.

## What This Option Does NOT Do Well

- Content behind authentication (LinkedIn profile pages, paywalled databases, internal enterprise job boards) is not accessible. The search sees the public web only.
- Google PSE does not guarantee freshness — pages may be indexed stale.
- 100 free queries/day is consumed fast in testing. Set up billing from day one.
- Coverage blind spots: non-indexed small sites, non-English content (important for Swiss German/French market), recently launched products (not yet indexed).

## Consequences

- Two PSE configurations must be created: one for job research (job board domains), one for competitor checking (product/startup directories).
- All search results must include the source URL in the output — this is a hard requirement to prevent hallucination (see challenges.md, Challenge 11).
- Search calls must be batched where possible and results cached to avoid burning the daily free quota during development.
- The competitor check output must explicitly state "no obvious public competitor found in sources checked" rather than "no competitor exists."
