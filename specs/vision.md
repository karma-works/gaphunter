# Vision

## What it is

An AI agent you prompt with a set of constraints — geography, industry vertical, what to exclude, what complexity level you want — and it returns a ranked shortlist of specific startup ideas, each validated against real job/market data, checked for competitor existence, and stress-tested by an adversarial critique layer. The output is a decision-ready brief per idea, not a list of suggestions to research yourself.

## What it is not

- **Not a generic idea generator**: It does not produce "build an app for X" without grounding in real data.
- **Not a market research dashboard**: It is not a tool for ongoing monitoring. It produces a point-in-time research sprint.
- **Not a business plan generator**: It stops at validated idea brief + confidence score. It does not write pitch decks, financial models, or GTM plans.
- **Not a general-purpose research agent**: The agent is specialized. It answers one question: "Is there a real, unoccupied market gap for an AI agent to do this specific job?"
- **Not a consulting service**: No human in the loop. Fully automated output.

## Primary user

**Archetype: Technical solo founder or small founding team.**

Specific situation: Has AI/engineering capability, wants to build a productized AI agent business, but doesn't have a validated idea yet. Is willing to test several ideas but doesn't want to waste months building in the wrong direction. Probably has 2–4 weeks to decide before committing to a build. Switzerland-based or targeting Swiss/DACH market is the launch context but the product is geography-agnostic.

## Secondary users

| User | Situation | Relationship to primary |
|---|---|---|
| VC/accelerator analyst | Wants to see the deal flow in a specific vertical | Uses output to scan for investable white spaces |
| Enterprise innovation team | Tasked with finding AI automation opportunities internally | Uses agent to identify which internal processes could be productized |
| Consultant | Advising clients on AI readiness | Uses output as a starting point for client conversations |

Secondary users are post-MVP. Primary user is the only one that matters for v1.

## Success criteria (MVP)

1. Given a constraint set, the agent returns ≥3 distinct, non-overlapping idea briefs within 5 minutes.
2. Each idea brief includes: job description sourced from real data, competitor check result (name competitors or confirm gap), adversarial critique (at least 2 specific objections), and a confidence score.
3. At least 70% of returned ideas pass a manual sanity check by the user (i.e., are real jobs that exist, not hallucinated).
4. The competitor check correctly identifies a known competitor when one exists (test with planted examples).
5. A user with no prior context can run the agent end-to-end without instructions beyond the prompt format.
