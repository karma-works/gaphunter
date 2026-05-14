# ADR-004: Web Search - Brave Search API

**Status:** Decided, replaces the earlier Google Custom Search API decision
**Date:** 2026-05-14

## Context

GapHunter needs live web search for two distinct purposes:

1. **Job research**: Find public job postings and role descriptions matching user constraints.
2. **Competitor checks**: Determine whether an AI agent product already exists for a specific job type.

The first implementation attempted Google Custom Search JSON API with Programmable Search Engines. That path is no longer suitable because Google documents Custom Search JSON API as closed to new customers, and project-level API enablement plus API keys still returned access-denied responses in our setup.

Alternatives evaluated: Brave Search API, SerpAPI, Google Agent Search, legacy Google Custom Search API, Playwright/browser automation, and direct LinkedIn/job-board APIs.

## Decision

Use Brave Search API as the MVP live web research backend.

The application exposes provider selection through `SEARCH_PROVIDER`, with `brave` as the intended live provider and `demo` as the safe fallback. The implementation keeps the existing normalized `SearchResult` boundary so another provider can be added without changing pipeline synthesis.

Required runtime configuration:

- `SEARCH_PROVIDER=brave`
- `BRAVE_SEARCH_API_KEY`
- Optional: `BRAVE_SEARCH_COUNTRY`, default `US`
- Optional: `BRAVE_SEARCH_LANG`, default `en`

## Rationale

- Brave returns structured JSON directly from its own independent web index.
- The API supports web search, freshness filtering, country/language targeting, safe search, site operators, pagination, extra snippets, and AI-oriented context endpoints.
- It is simpler for the MVP than Agent Search because it does not require pre-indexing curated website data stores.
- It avoids depending on Google Custom Search API access for a new customer.
- It is a cleaner fit than SerpAPI when the need is broad web discovery rather than Google-specific SERP modules.

## Why Not SerpAPI For MVP

SerpAPI is useful and also returns structured JSON, including `organic_results`, answer boxes, local results, knowledge graph data, news, images, shopping, and many Google-specific verticals. It is a good option if GapHunter later needs Google Jobs-style surfaces or many search engines behind one API.

For the MVP, SerpAPI adds dependence on parsed Google SERPs and a monthly quota model. GapHunter's first live search path needs broad, source-linked web evidence more than rich Google SERP modules.

## What This Option Does Not Do Well

- It does not provide authenticated LinkedIn/job-board content.
- It does not prove that no competitor exists; it only checks public indexed web results.
- Search result quality may differ from Google for some local or vertical-specific queries.
- The MVP still needs query tuning, caching, rate-limit handling, and source scoring.

## Consequences

- All search results must continue to include source URLs. Results without URLs are dropped.
- Competitor output must say that no obvious public competitor was found in searched sources, not that no competitor exists.
- Runtime health stays in `demo` mode until `BRAVE_SEARCH_API_KEY` is configured.
- The next production hardening step is caching search responses to control cost and latency.
