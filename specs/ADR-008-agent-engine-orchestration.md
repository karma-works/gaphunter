# ADR-008: Agent Orchestration - Cloud Run Thin Shell + Vertex AI Agent Engine

**Status:** Decided
**Date:** 2026-05-15

## Context

GapHunter currently runs a lightweight pipeline inside the Cloud Run FastAPI service. That was useful for scaffolding the product surface, deployment, Firestore persistence, and Brave Search integration, but it is not the target architecture for the agentic workflow.

The product needs a multi-step research agent that can plan, call tools, inspect source evidence, synthesize structured ideas, critique them, score research coverage, and support later refinement. Keeping that reasoning loop inside Cloud Run would make the web service responsible for agent internals, long-running orchestration, progress semantics, and model/tool execution. That is the wrong ownership boundary.

## Decision

Use Cloud Run as a thin product shell and Vertex AI Agent Engine as the orchestrator for the agentic workflow.

Cloud Run owns:

- Browser UI and HTTP API.
- Authentication and request validation.
- Run creation and public run status endpoints.
- Calling Agent Engine.
- Reading run state and results for display.
- Product-level authorization and rate limits.

Cloud Run does not own:

- Prompt chains.
- Internal planning loops.
- Tool sequencing.
- Agent scratch state.
- Private reasoning traces.
- Synthesis, critique, or scoring logic.

Vertex AI Agent Engine owns:

- The orchestrator agent.
- Sub-agent composition.
- Tool calls to Brave Search and future research tools.
- Gemini model calls.
- Progress event generation.
- Direct Firestore writes for run status, progress events, source evidence, and final results.
- Future session-aware refinement workflows.

## Workflow

1. User submits a constraint prompt through the Cloud Run UI.
2. Cloud Run validates the request, creates a `run_id`, writes an initial `queued` record, and invokes Agent Engine with `run_id`, user/session identity, and the prompt.
3. Agent Engine executes the research workflow:
   - `ConstraintAgent`: converts the prompt into structured constraints.
   - `ResearchPlanner`: chooses query strategy and source priorities.
   - `JobResearchAgent`: proves target jobs/tasks exist using public source evidence.
   - `CompetitorAgent`: searches for existing products that address each candidate job.
   - `SynthesisAgent`: creates idea briefs grounded in job and competitor evidence.
   - `CritiqueAgent`: produces data-grounded objections.
   - `ScoringAgent`: computes research coverage scores.
   - `Finalizer`: writes a strict final result matching the public `RunResult` contract.
4. Agent Engine writes stage-level progress events directly to Firestore.
5. Cloud Run serves `GET /runs/{run_id}` and progress views by reading Firestore.
6. The UI displays progress summaries, source snippets, source URLs, and final ideas, but never private reasoning traces.

## Chatbot And Refinement

The first production interaction remains async "run research" with progress, not a generic chatbot.

Chat comes next as refinement over an existing run/session. Examples:

- "Relax geography to DACH."
- "Exclude regulated healthcare."
- "Deepen idea 2."
- "Find more competitors for idea 1."
- "Turn this brief into a validation checklist."

The refinement chat should use Agent Engine session context after the first run workflow is reliable. The chatbot should expose user-visible decisions, source evidence, and stage summaries, but not chain-of-thought or private scratch work.

## Firestore Ownership

Agent Engine writes directly to Firestore.

Rationale:

- Long-running progress belongs close to the orchestrator.
- Cloud Run should not proxy every internal stage update.
- Agent Engine can persist partial progress if Cloud Run requests time out or the browser disconnects.
- Firestore becomes the shared contract between the product shell and agent runtime.

Required guardrails:

- Use a dedicated Agent Engine service account with least-privilege Firestore access.
- Separate user-facing result documents from internal diagnostic records.
- Do not write private reasoning traces to user-visible documents.
- Store source URLs, snippets, and stage summaries; avoid storing raw hidden reasoning.
- Include `run_id`, `user_id` or anonymous session ID, timestamps, status, and schema version on every write.

## Search Layer

Keep Brave Search as the broad web discovery tool inside Agent Engine for the MVP.

Vertex AI Search / Agent Search can be evaluated later for curated source sets, but it should not replace Brave Search until the product has a known set of high-value domains to index.

## Consequences

- The existing local pipeline should be refactored behind an `AgentGateway` boundary before Agent Engine deployment.
- Cloud Run can keep a local fake or local pipeline implementation for tests and development, but production should call Agent Engine.
- The public API contract should remain stable while the agent implementation moves out of Cloud Run.
- Firestore schema must support queued/running/completed/failed states and progress events.
- Agent deployment, versioning, and rollback become part of release management.
- Observability must span Cloud Run request logs, Agent Engine logs/traces, and Firestore run records.

## Open Implementation Tasks

- Define Firestore collections for runs, progress events, source evidence, and agent diagnostics.
- Add `AgentGateway` abstraction to Cloud Run.
- Build a local fake gateway for tests.
- Build a deployed Agent Engine gateway for production.
- Refactor the current pipeline into Agent Engine-compatible modules.
- Deploy the first minimal Agent Engine orchestrator.
- Route `POST /runs` through Agent Engine.
- Add progress polling to the UI.
- Add schema-versioned final result validation.
