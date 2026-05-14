# ADR-005: Runtime — Cloud Run

**Status:** Decided
**Date:** 2026-05-14

## Context

The agent runs on-demand: a user submits constraints, the agent runs for 2–5 minutes, returns output. There is no continuous background processing in v1. The runtime needs to: run a Python 3.12 ADK application, accept HTTP requests, handle runs that take several minutes, and cost nothing when idle.

Alternatives: Cloud Run, GKE, Compute Engine VM, Vertex AI Pipelines, Cloud Functions.

## Decision

Deploy the agent as a containerized Python application on Cloud Run.

## Rationale

- Pay-per-use: no idle cost. Correct for a tool that runs sporadically in v1.
- No cluster management. No ops overhead vs. GKE.
- Supports long-running requests up to 3,600 seconds (1 hour) — more than enough for a 5-minute agent run.
- Container-based deployment means local dev environment matches production (Dockerfile is the contract).
- Native integration with Firestore, Secret Manager (for API keys), and Firebase Auth via Google Cloud IAM.

GKE was rejected: overkill for a stateless on-demand workload. Would add significant ops complexity.

Vertex AI Pipelines was rejected: designed for ML training pipelines, not interactive web agents. Adds scheduling/orchestration complexity that isn't needed.

Cloud Functions was rejected: 9-minute max timeout (2nd gen) is tight for a 5-minute agent run with no headroom. Also more complex to package with ADK dependencies.

## What This Option Does NOT Do Well

- Cold start latency: 1–3s on first request. Acceptable for a tool where runs take minutes, not milliseconds.
- Stateless: no shared memory between requests. All state must go to Firestore. This is a feature, not a bug — it forces clean architecture.
- Streaming responses to the browser require SSE (Server-Sent Events) or WebSockets, which add frontend complexity. For MVP, async run + polling (or email notification) is simpler.

## Consequences

- Dockerfile is the deployment artifact. Keep it simple: base Python image, pip install requirements, run Streamlit or Flask.
- All secrets (Gemini API key, Brave Search API key, Firebase credentials) must be stored in Secret Manager and injected as environment variables at runtime. Never hardcode.
- Request timeout must be set to at least 600 seconds in Cloud Run config to handle slow runs.
- Min instances = 0 in v1 (cost optimization). Set to 1 if cold starts become a UX problem post-launch.
