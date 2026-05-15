# Specs — AI Business Idea Generation Agent

## Overview

An AI agent that takes user constraints, researches real job markets and competitor landscapes, and returns ranked, adversarially-critiqued startup idea briefs — specifically targeting "AI agent for rent" plays where a human knowledge-worker job can be productized as a deployed AI agent.

## Documents

| File | Description |
|---|---|
| [thesis.md](thesis.md) | Why this product needs to exist — the structural problem, why existing tools fail, the claim |
| [vision.md](vision.md) | What it is, who it's for, what MVP success looks like |
| [product.md](product.md) | User types, core flows, feature list, monetization hypothesis |
| [challenges.md](challenges.md) | 12 adversarial challenges against the core assumptions — includes the risks that could kill the project |
| [tech-stack.md](tech-stack.md) | Full recommended stack with rationale and explicit "not using" table |
| [ADR-001-data-storage.md](ADR-001-data-storage.md) | Firestore as primary data store |
| [ADR-002-agent-framework.md](ADR-002-agent-framework.md) | Google ADK (Python) as agent orchestration framework |
| [ADR-003-llm-strategy.md](ADR-003-llm-strategy.md) | Gemini 2.0 Flash (research) + Gemini 2.5 Pro (synthesis + critique) |
| [ADR-004-web-search.md](ADR-004-web-search.md) | Brave Search API as MVP live web research backend |
| [ADR-005-runtime.md](ADR-005-runtime.md) | Cloud Run for serverless deployment |
| [ADR-006-auth.md](ADR-006-auth.md) | Firebase Auth + Google Sign-In |
| [ADR-007-gtm-mvp-scope.md](ADR-007-gtm-mvp-scope.md) | Personal tool first, productize after output quality is validated |
| [ADR-008-agent-engine-orchestration.md](ADR-008-agent-engine-orchestration.md) | Cloud Run thin shell with Vertex AI Agent Engine orchestration |
| [implementation-plan.md](implementation-plan.md) | Week-by-week Phase 0 plan + Phase 1/2 outlines |

## Key decisions

- **Stack is Google-native**: ADK + Gemini + Cloud Run + Firestore + Firebase Auth — consistent, manageable, no third-party LLM or auth vendors
- **Two-model LLM strategy**: Flash for research loops (speed + cost), Pro for synthesis and critique (quality where it matters)
- **Live web search**: Brave Search API for MVP job research and competitor checking
- **Agent orchestration boundary**: Cloud Run is the product/API shell; Vertex AI Agent Engine owns the agentic workflow and writes progress/results to Firestore
- **Personal tool first**: No payment infrastructure until output quality is manually validated (Phase 0 success criterion: ≥70% of ideas pass manual review)
- **Source URL is mandatory**: Every job and competitor result must include a source URL; results without one are dropped (anti-hallucination hard constraint)
- **Scores are coverage, not confidence**: "Research coverage score" not "confidence score" — prevents founders from treating output as a green light to build

## Suggested project names

- **GapHunter** — direct, describes the core function (finding gaps)
- **VentureScope** — slightly more aspirational, scope = research + vision
- **IdeaRadar** — friendly, approachable, implies scanning/finding
- **NicheForge** — implies creating something new in a specific niche
- **SignalFound** — references the thesis language ("the signal")
- **MarketGap.ai** — literal, SEO-friendly, clear
- **OpportunityAgent** — describes the product type directly
- **WhiteSpace** — design/strategy term for unoccupied market space

**Recommendation: GapHunter** — short, memorable, describes the exact value (finds market gaps), not yet saturated as a product name.

## Critical validation before writing code

Spend 4 hours manually doing what the agent would do on the Swiss example constraint. If you find ≥2 compelling, gap-confirmed AI-agent-for-rent opportunities: build it. If not: the core hypothesis needs revision before any code is written.
