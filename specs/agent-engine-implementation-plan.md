# Agent Engine Implementation Plan

**Status:** Draft implementation plan
**Date:** 2026-05-15
**Related ADR:** [ADR-008: Agent Orchestration - Cloud Run Thin Shell + Vertex AI Agent Engine](ADR-008-agent-engine-orchestration.md)

## Goal

Move GapHunter from an in-process Cloud Run research pipeline to an architecture where Cloud Run is a thin product shell and Vertex AI Agent Engine orchestrates the agentic workflow.

The migration must preserve the existing public app while progressively moving reasoning, tool use, progress events, and final result generation into Agent Engine.

## Non-Goals

- Do not build a generic chatbot in the first migration phase.
- Do not expose private reasoning traces in the UI or Firestore user-facing documents.
- Do not replace Brave Search with Vertex AI Search yet.
- Do not require Firebase Auth before the Agent Engine migration works for anonymous/demo use.
- Do not remove the local deterministic pipeline until Agent Engine is deployed and verified.

## Target Architecture

Cloud Run:

- Serves the UI and HTTP API.
- Creates run IDs.
- Validates request payloads.
- Invokes an `AgentGateway`.
- Reads run status, progress, and results from Firestore.
- Owns user-facing authorization and rate limits.

Agent Engine:

- Runs the orchestrator agent.
- Calls sub-agents/tools.
- Calls Gemini models.
- Calls Brave Search.
- Writes progress events and final results directly to Firestore.

Firestore:

- Stores run documents.
- Stores progress events.
- Stores source evidence.
- Stores internal diagnostics separately from user-facing data.

## Phase 1: Firestore Run Contract

Purpose: define the stable persistence contract before changing execution.

Tasks:

- Add explicit run status values: `queued`, `running`, `completed`, `failed`.
- Define collection layout:
  - `runs/{run_id}`: public run summary and final result.
  - `runs/{run_id}/events/{event_id}`: user-visible progress events.
  - `runs/{run_id}/sources/{source_id}`: source URLs, snippets, provider, query, and timestamps.
  - `agent_diagnostics/{run_id}/events/{event_id}`: internal diagnostics, not displayed by default.
- Add schema version fields to run documents and final results.
- Add helper methods in the storage layer for:
  - creating a queued run,
  - marking running,
  - appending progress events,
  - appending source evidence,
  - completing with a validated `RunResult`,
  - failing with a safe error summary.

Expected files:

- `app/models.py`
- `app/storage.py`
- `tests/test_storage.py`

Acceptance criteria:

- Unit tests cover all run state transitions.
- Existing `POST /runs` and `GET /runs/{id}` still work.
- Existing completed `RunResult` response shape remains compatible with current UI.

Rollback:

- Keep current `RunStore.save()` and `RunStore.get()` behavior until new helpers are proven.

## Phase 2: AgentGateway Boundary

Purpose: make Cloud Run call an agent boundary instead of directly owning pipeline execution.

Tasks:

- Add `AgentGateway` protocol/interface.
- Add `LocalPipelineAgentGateway` that wraps the current in-process pipeline.
- Add `FakeAgentGateway` for tests.
- Update `POST /runs` to call the configured gateway.
- Add `AGENT_BACKEND=local|agent_engine|fake`, default `local`.
- Keep synchronous behavior for local mode while preserving the future async run contract.

Expected files:

- `app/agent_gateway.py`
- `app/settings.py`
- `app/main.py`
- `tests/test_agent_gateway.py`
- `tests/test_pipeline.py`

Acceptance criteria:

- Existing UI and API behavior remain unchanged in `AGENT_BACKEND=local`.
- Tests can run without network or Google credentials.
- Cloud Run can still deploy and serve the current app.

Rollback:

- Set `AGENT_BACKEND=local` to keep using the current pipeline.

## Phase 3: Progress API And UI Polling

Purpose: make the product shell ready for long-running Agent Engine runs.

Tasks:

- Add `GET /runs/{run_id}/events`.
- Change `POST /runs` to support queued/running responses once Agent Engine mode is enabled.
- Add UI polling for run status and progress events.
- Display stage summaries:
  - queued,
  - parsing constraints,
  - planning research,
  - researching jobs,
  - checking competitors,
  - synthesizing ideas,
  - critiquing,
  - scoring,
  - completed or failed.
- Keep source URLs and snippets visible when available.

Expected files:

- `app/main.py`
- `app/models.py`
- `app/storage.py`
- `tests/test_pipeline.py` or `tests/test_routes.py`

Acceptance criteria:

- UI still supports the current one-click run flow.
- Events render without page reload.
- No private reasoning field is displayed or returned by public endpoints.

Rollback:

- Hide progress polling in UI while keeping backend endpoints available.

## Phase 4: Agent Engine Scaffold

Purpose: create a minimal deployable Agent Engine orchestrator before porting the full workflow.

Tasks:

- Add an agent package separate from the Cloud Run app.
- Implement a minimal orchestrator that:
  - accepts `run_id`, prompt, and session/user identity,
  - writes `running` and one progress event to Firestore,
  - writes a deterministic final `RunResult`,
  - writes `completed`.
- Add deployment script or Make target for Agent Engine.
- Add service account and IAM notes for Firestore write access.
- Store required runtime config without hardcoded secrets.

Expected files:

- `agent/`
- `agent/orchestrator.py`
- `agent/tools/`
- `agent/deploy.py` or `scripts/deploy-agent-engine.sh`
- `specs/agent-engine-operations.md` if setup details become substantial.

Acceptance criteria:

- Agent Engine deployment succeeds in `gaphunter-496315`.
- Minimal agent can be invoked manually.
- Firestore shows expected run status and progress writes.
- No Cloud Run route depends on the minimal agent yet.

Rollback:

- Delete or ignore the Agent Engine deployment; Cloud Run remains on `AGENT_BACKEND=local`.

## Phase 5: AgentEngineGateway

Purpose: connect Cloud Run to the deployed Agent Engine without moving all agent logic at once.

Tasks:

- Implement `AgentEngineGateway`.
- Configure endpoint/resource ID via environment variables.
- Update Cloud Run deployment configuration:
  - `AGENT_BACKEND=agent_engine` for production when ready,
  - `AGENT_BACKEND=local` for rollback.
- Ensure Cloud Run creates `queued` run records before invoking Agent Engine.
- Ensure Agent Engine writes progress/final state directly to Firestore.

Expected files:

- `app/agent_gateway.py`
- `app/settings.py`
- `.github/workflows/deploy.yml`
- `README.md`

Acceptance criteria:

- `POST /runs` starts an Agent Engine run.
- UI shows progress events written by Agent Engine.
- `GET /runs/{id}` returns final results from Firestore.
- Switching `AGENT_BACKEND=local` restores current behavior.

Rollback:

- Revert Cloud Run environment to `AGENT_BACKEND=local`.

## Phase 6: Port The Research Workflow

Purpose: move real agentic work into Agent Engine.

Tasks:

- Port or replace current pipeline stages with Agent Engine-compatible components:
  - `ConstraintAgent`,
  - `ResearchPlanner`,
  - `JobResearchAgent`,
  - `CompetitorAgent`,
  - `SynthesisAgent`,
  - `CritiqueAgent`,
  - `ScoringAgent`,
  - `Finalizer`.
- Keep Brave Search as a tool.
- Add Gemini structured output for:
  - constraints,
  - job candidates,
  - competitor analysis,
  - idea briefs,
  - critiques.
- Validate every final result against the shared `RunResult` schema.
- Drop search results without URLs.
- Persist source evidence separately from final idea briefs.

Expected files:

- `agent/orchestrator.py`
- `agent/models.py`
- `agent/tools/search.py`
- `agent/tools/firestore.py`
- `agent/prompts/`
- shared schema module if needed

Acceptance criteria:

- A run produces source-backed idea briefs using Gemini and Brave Search.
- Critiques are grounded in source evidence.
- Research coverage score is explained as coverage, not business viability.
- Agent failure produces safe `failed` state with a user-readable error.

Rollback:

- Keep minimal deterministic Agent Engine finalizer or switch Cloud Run back to local pipeline.

## Phase 7: Production Hardening

Purpose: make the Agent Engine path reliable enough for repeated use.

Tasks:

- Add structured logs with `run_id`.
- Add retry policy for Brave Search and transient Gemini failures.
- Add per-run query budget.
- Add search result caching.
- Add timeout handling and partial-result failure behavior.
- Add basic cost telemetry per run.
- Add manual evaluation checklist for output quality.

Acceptance criteria:

- A single failed search call does not fail the entire run.
- Runs have bounded query count and model call count.
- Logs can reconstruct a failed run without exposing private reasoning to users.

Rollback:

- Keep production behind `AGENT_BACKEND=local` until hardening passes manual smoke tests.

## Phase 8: Refinement Chat

Purpose: add conversation after the first-run workflow is reliable.

Tasks:

- Add chat/refinement endpoint in Cloud Run.
- Use Agent Engine session context for existing runs.
- Support scoped refinement commands:
  - relax constraints,
  - deepen a selected idea,
  - expand competitor research,
  - create validation checklist.
- Persist chat-visible messages separately from internal reasoning.

Acceptance criteria:

- Users can refine an existing run without starting from scratch.
- Chat outputs cite prior run evidence or new source evidence.
- Chat does not become a generic unsupported assistant.

Rollback:

- Hide chat UI while preserving base run workflow.

## Immediate Next Build Step

Start with Phase 1 and Phase 2 together:

1. Add the Firestore run contract and state transition helpers.
2. Add `AgentGateway` with `LocalPipelineAgentGateway`.
3. Keep production on local behavior.
4. Add tests proving the Cloud Run product shell can route through the gateway without knowing pipeline internals.
