# ADR-002: Agent Framework — Google ADK (Python)

**Status:** Decided
**Date:** 2026-05-14

## Context

The product requires a multi-step agentic pipeline: constraint parsing → job research (multiple search calls) → competitor checking (multiple search calls) → idea synthesis → adversarial critique → scoring. This pipeline needs tool use (search API calls), sub-agent composition (critique as a separate agent), and streaming output for UX.

Alternatives considered: LangChain, LlamaIndex, bare Gemini API with custom orchestration, Vertex AI Agent Builder, Google ADK.

## Decision

Use Google ADK (google/adk-python) as the agent orchestration framework.

## Rationale

- ADK is Python-native and code-first — the pipeline is explicit code, not low-code config. This makes debugging tractable.
- Multi-agent composition is built in. The critique layer can be a separate `Agent` that receives a brief and returns objections, called as a sub-agent from the main orchestrator.
- Function calling / tool use is first-class. Wrapping the Brave Search API as an ADK tool is straightforward.
- ADK targets Vertex AI for managed deployment but runs locally and on Cloud Run without Vertex overhead — useful for keeping infra simple in v1.
- Google-native: Gemini models are first-class in ADK, no adapter layers needed.

LangChain was rejected: heavy dependency, not Google-native, adds abstraction cost for no clear benefit over ADK for this use case.

Vertex AI Agent Builder was rejected: high abstraction hides the pipeline, hard to debug, and locks into Vertex AI for deployment before we know if the product needs that scale.

## What This Option Does NOT Do Well

- ADK is newer than LangChain and has a smaller community. Fewer StackOverflow answers, fewer third-party integrations.
- API surface may change — ADK is under active development. Pin versions carefully.
- Not suitable for non-Python runtimes. If a TypeScript frontend wants to run the agent, it needs a separate API layer.

## Consequences

- Python 3.12 is the target runtime.
- Agent pipeline is defined as ADK `Agent` + `Tool` objects in code.
- Sub-agents (e.g., critique agent) are composed using ADK's multi-agent patterns.
- Deployment to Cloud Run requires a Dockerfile that installs ADK and its dependencies.
- Tests must mock ADK tool calls — check ADK's testing utilities before writing custom mocks.
