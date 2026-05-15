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

```
Browser
  │
  ▼
Cloud Run (thin product shell)
  ├── Serves UI and HTTP API
  ├── Validates request payloads
  ├── Creates run IDs, writes queued record
  ├── Calls AgentGateway.start_run(run_id, prompt)
  ├── Reads run status + results from Firestore
  └── Owns user-facing auth + rate limits

AgentGateway (protocol boundary)
  ├── LocalPipelineAgentGateway  ← AGENT_BACKEND=local
  ├── AgentEngineGateway         ← AGENT_BACKEND=agent_engine
  └── FakeAgentGateway           ← AGENT_BACKEND=fake (tests)

Vertex AI Agent Engine
  ├── Runs orchestrator agent
  ├── Calls sub-agents + tools
  ├── Calls Gemini models
  ├── Calls Brave Search
  └── Writes directly to Firestore:
        runs/{run_id}                        ← status, final result
        runs/{run_id}/events/{event_id}      ← user-visible progress
        runs/{run_id}/sources/{source_id}    ← source evidence
        agent_diagnostics/{run_id}/...       ← internal only

Firestore (shared contract)
  └── Single source of truth for all run state
```

Cloud Run does not own: prompt chains, planning loops, tool sequencing, agent scratch state, private reasoning traces, synthesis/critique/scoring logic.

## API Contract (all backends)

`POST /runs` returns immediately with `{run_id, status: "queued"}` (HTTP 202) for all backends. Local mode writes the completed result synchronously before returning, but the response shape is always the same. The UI polls `GET /runs/{id}` for the result.

`GET /runs/{id}` returns a `RunStatusResponse` with `status` and optional `ideas`, `events`, and `progress`. `RunResult` remains the internal completed-state type; `RunStatusResponse` is the public API type that accommodates all states.

## Firestore Write Rules

- `create_queued_run()` uses `.set()` — full document creation.
- All state-transition helpers (`mark_running`, `complete_with_result`, `fail_with_error`, `append_event`, `append_source`) use `.update()` — partial updates only. This prevents Cloud Run and Agent Engine from clobbering each other's fields.
- State transitions use Firestore conditional updates (transactions with preconditions): `mark_running` succeeds only if current status is `queued`; `complete_with_result` succeeds only if current status is `running`. This prevents overwriting terminal states on retry.

## Phase 1: Firestore Run Contract

Purpose: define the stable persistence contract before changing execution.

Tasks:

- Add explicit run status values: `queued`, `running`, `completed`, `failed`.
- Define collection layout:
  - `runs/{run_id}`: public run summary and final result.
  - `runs/{run_id}/events/{event_id}`: user-visible progress events.
  - `runs/{run_id}/sources/{source_id}`: source URLs, snippets, provider, query, and timestamps.
  - `agent_diagnostics/{run_id}/events/{event_id}`: internal diagnostics, not displayed by default.
- Define event ordering scheme: event IDs use server-timestamp-ordered queries (`order_by("created_at")`), or structured IDs using a per-run monotonic sequence counter. Choose and document before writing any event collection code. See TODOS.md TODO-001.
- Add schema version fields to run documents and final results. All new fields are `Optional` with defaults so existing documents deserialize without error.
- Add idempotency support: `POST /runs` accepts an optional `idempotency_key`; if a run with that key already exists, return the existing `run_id` instead of creating a duplicate.
- Add helper methods in the storage layer for:
  - creating a queued run (`set()`),
  - marking running (`update()`, conditional on `queued`),
  - appending progress events (`update()`),
  - appending source evidence (`update()`),
  - completing with a validated `RunResult` (`update()`, conditional on `running`),
  - failing with a safe error summary (`update()`, conditional on non-terminal state).
- Add `RunStatusResponse` model alongside `RunResult`: `{run_id, status, ideas?, events?, progress?}`. Update `GET /runs/{id}` to use `RunStatusResponse` as the response model.
- Update Firestore client initialization: log and raise on init failure when `GCP_PROJECT_ID` is set. A misconfigured Firestore client must not silently fall back to in-memory.

Expected files:

- `app/models.py`
- `app/storage.py`
- `tests/test_storage.py`

Acceptance criteria:

- Unit tests cover all run state transitions.
- Conditional update guards prevent overwriting terminal states.
- `GET /runs/{id}` returns a valid `RunStatusResponse` for `queued`, `running`, `completed`, and `failed` states without raising.
- Existing `POST /runs` and `GET /runs/{id}` still work.
- Existing completed `RunResult` response shape remains compatible with current UI.
- Firestore init failure raises rather than falling back silently when `GCP_PROJECT_ID` is configured.

Rollback:

- Keep current `RunStore.save()` and `RunStore.get()` behavior until new helpers are proven.

## Phase 2: AgentGateway Boundary

Purpose: make Cloud Run call an agent boundary instead of directly owning pipeline execution.

Tasks:

- Add `AgentGateway` protocol/interface with method `start_run(run_id: str, request: RunRequest) -> None`. The gateway writes all results to Firestore; it never returns a `RunResult` directly.
- Add `LocalPipelineAgentGateway`: runs the current in-process pipeline synchronously, then writes `running` → completed/failed state to Firestore via Phase 1 helpers before returning.
- Add `FakeAgentGateway` for tests: accepts a configurable canned result or failure.
- Update `POST /runs` to: create a `queued` run record, invoke the configured gateway, return `{run_id, status: "queued"}` (HTTP 202) immediately. The UI polls for the result.
- Add `AGENT_BACKEND=local|agent_engine|fake`, default `local`.

Expected files:

- `app/agent_gateway.py`
- `app/settings.py`
- `app/main.py`
- `tests/test_agent_gateway.py`
- `tests/test_pipeline.py`

Acceptance criteria:

- `POST /runs` returns `{run_id, status: "queued"}` for all backends.
- `GET /runs/{id}` returns the completed result after the local gateway finishes.
- Tests can run without network or Google credentials.
- Cloud Run can still deploy and serve the current app.

Rollback:

- Set `AGENT_BACKEND=local` to keep using the current pipeline.

## Phase 3: Progress API and UI Polling

Purpose: make the product shell ready for long-running Agent Engine runs.

Tasks:

- Add `GET /runs/{run_id}/events`: returns ordered list of user-visible progress events. Returns 404 if run not found (not an empty list — callers use 404 to distinguish "run missing" from "run started but no events yet").
- Add UI polling: on submit, receive `run_id`, then poll `GET /runs/{id}` every 2 seconds until status is `completed` or `failed`. Add a client-side timeout of 10 minutes; display a "taking longer than expected" message at 5 minutes.
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
- `tests/test_routes.py`

Acceptance criteria:

- UI supports the current one-click run flow end to end.
- Events render without page reload.
- UI does not poll indefinitely — client-side timeout at 10 minutes.
- `GET /runs/{id}/events` returns 404 for unknown run IDs.
- No private reasoning field is displayed or returned by public endpoints.

Rollback:

- Hide progress polling in UI while keeping backend endpoints available.

## Phase 4: Agent Engine Scaffold

Purpose: verify Agent Engine is the right orchestration target and create a minimal deployable orchestrator.

**Spike gate (do this first, before writing any agent code):**

Deploy a hello-world Agent Engine function to `gaphunter-496315`. Verify:
- Invocation succeeds from Cloud Run.
- IAM (Agent Engine service account → Firestore write access) is confirmed with a test write.
- Invocation latency is acceptable.
- Local development workflow is viable: can the orchestrator be tested without deploying? Document the answer in `README.md` or `specs/agent-engine-operations.md`. See TODOS.md TODO-002.

If the spike reveals that Agent Engine is not the right target (maturity, IAM complexity, cost, local dev friction), evaluate Cloud Tasks + Cloud Run jobs as the alternative before proceeding to Phase 5.

Tasks:

- **Spike**: deploy hello-world Agent Engine function, verify IAM + invocation + local dev loop.
- Create IAM binding: Agent Engine service account with `roles/datastore.user` on `gaphunter-496315`. This is a required task, not optional documentation. Verify with a test Firestore write before Phase 5.
- Add an `agent/` package separate from the Cloud Run app.
- Define shared schema strategy: `agent/` imports from `app/models.py` directly (as a sub-package), or a dedicated `gaphunter_models` package. Decide and document before Phase 6 writes any agent output. Both packages must use the same `RunResult` definition.
- Implement a minimal orchestrator that:
  - accepts `run_id`, prompt, and session/user identity,
  - writes `running` and one progress event to Firestore via Phase 1 helpers,
  - writes a deterministic final `RunResult`,
  - writes `completed`.
- Add deployment script or Make target for Agent Engine.
- Store required runtime config (Gemini API key, Brave Search key) via Secret Manager — no hardcoded secrets.

Expected files:

- `agent/`
- `agent/orchestrator.py`
- `agent/tools/`
- `agent/deploy.py` or `scripts/deploy-agent-engine.sh`
- `specs/agent-engine-operations.md`

Acceptance criteria:

- **Spike passes**: Agent Engine hello-world deployed and invokable from Cloud Run.
- Agent Engine service account can write to Firestore (verified before Phase 5).
- Local dev workflow documented: developer can run orchestrator tests without deploying to GCP.
- Shared schema strategy decided and documented.
- Minimal agent deployed and manually invokable.
- Firestore shows expected run status and progress writes.
- No Cloud Run route depends on the minimal agent yet.

Rollback:

- Delete or ignore the Agent Engine deployment; Cloud Run remains on `AGENT_BACKEND=local`.
- If spike fails: revisit ADR-008 and evaluate Cloud Tasks alternative.

## Phase 5: AgentEngineGateway

Purpose: connect Cloud Run to the deployed Agent Engine without moving all agent logic at once.

Tasks:

- Implement `AgentEngineGateway`.
- Configure endpoint/resource ID via environment variables.
- Update Cloud Run deployment configuration:
  - `AGENT_BACKEND=agent_engine` for production when ready,
  - `AGENT_BACKEND=local` for rollback.
- Ensure Cloud Run creates `queued` run records before invoking Agent Engine.
- Ensure Agent Engine writes progress/final state directly to Firestore via Phase 1 helpers (`.update()`, conditional transitions).
- Add cost kill switch before enabling in production: enforce per-run limits (max Brave Search queries, max Gemini model calls). Abort and write `failed` if limits are exceeded. This must be in place before `AGENT_BACKEND=agent_engine` is used in production.

Expected files:

- `app/agent_gateway.py`
- `app/settings.py`
- `.github/workflows/deploy.yml`
- `README.md`

Acceptance criteria:

- `POST /runs` starts an Agent Engine run.
- UI shows progress events written by Agent Engine.
- `GET /runs/{id}` returns final results from Firestore.
- Per-run query and model call limits are enforced before production use.
- Switching `AGENT_BACKEND=local` restores current behavior.

Rollback:

- Revert Cloud Run environment to `AGENT_BACKEND=local`. Note: this does not roll back Firestore schema changes or UI polling assumptions — those stay in place.

## Phase 6a: Minimal Agent Engine Research Path

Purpose: one working end-to-end path through Agent Engine before adding all agents.

Tasks:

- Port or implement:
  - `ConstraintAgent`: converts prompt to structured constraints.
  - `JobResearchAgent`: calls Brave Search, returns job candidates with source URLs.
  - `Finalizer`: validates output against shared `RunResult` schema and writes `completed`.
- Add Gemini structured output for constraints and job candidates.
- Drop search results without URLs (hard constraint from challenges.md Challenge 11).
- Persist source evidence to `runs/{run_id}/sources/`.
- Validate every final result against the shared `RunResult` schema before writing.

Expected files:

- `agent/orchestrator.py`
- `agent/models.py`
- `agent/tools/search.py`
- `agent/tools/firestore.py`
- `agent/prompts/`

Acceptance criteria:

- A run produces at least one source-backed idea brief using Gemini and Brave Search.
- Agent failure produces safe `failed` state with a user-readable error.
- No result without a source URL reaches the output.

Rollback:

- Keep minimal deterministic Agent Engine finalizer or switch Cloud Run back to local pipeline.

## Phase 6b: Gap Confirmation

Purpose: add competitor analysis and idea synthesis to the Agent Engine path.

Tasks:

- Implement `CompetitorAgent`: searches for existing products per job candidate.
- Implement `SynthesisAgent`: creates idea briefs grounded in job and competitor evidence.
- Add Gemini structured output for competitor analysis and idea briefs.

Acceptance criteria:

- Ideas are marked `gap_confirmed` based on real competitor search results.
- Source evidence links ideas to specific job and competitor search results.
- Research coverage score is explained as coverage, not business viability.

## Phase 6c: Critique and Scoring

Purpose: complete the research workflow with critique and scoring.

Tasks:

- Implement `CritiqueAgent`: produces data-grounded objections (not generic).
- Implement `ScoringAgent`: computes research coverage scores.
- Implement `ResearchPlanner` if needed for query strategy.
- Add Gemini structured output for critiques and scores.

Acceptance criteria:

- Critiques are grounded in source evidence from the run, not generic.
- Research coverage score reflects actual source coverage, not business viability confidence.

## Phase 7: Production Hardening

Purpose: make the Agent Engine path reliable enough for repeated use.

Tasks:

- Add structured logs with `run_id` spanning Cloud Run requests, Agent Engine events, and Firestore writes.
- Add retry policy for Brave Search and transient Gemini failures (a single failed call does not fail the run).
- Refine per-run query budget introduced in Phase 5.
- Add search result caching: Firestore `search_cache` collection, key = `hash(query + date)`, TTL = 24 hours.
- Add timeout handling and partial-result failure behavior.
- Add cost telemetry per run.
- Add manual evaluation checklist for output quality.

Acceptance criteria:

- A single failed search call does not fail the entire run.
- Runs have bounded query count and model call count.
- Logs can reconstruct a failed run without exposing private reasoning to users.

Rollback:

- Keep production behind `AGENT_BACKEND=local` until hardening passes manual smoke tests.

## Phase 8: Refinement Chat

Purpose: add conversation after the first-run workflow is reliable.

**Decision gate:** Only start Phase 8 after Phase 7 is stable and there is evidence of user demand for refinement (run history shows repeated runs on the same constraint set, or direct user feedback). Do not start Phase 8 as a natural continuation of Phase 7.

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

Phase 1 first, then Phase 2. Do not combine them in a single PR — Phase 1 establishes the storage contract; Phase 2 introduces the execution boundary. Regressions are easier to isolate when these are separate.

**Phase 1 PR:**
1. Add `RunStatusResponse` model and update `GET /runs/{id}`.
2. Add `queued`, `running` to `RunStatus`.
3. Add Firestore state-transition helpers with `.update()` semantics and conditional guards.
4. Add idempotency key support to `POST /runs`.
5. Define event ordering scheme (see TODOS.md TODO-001).
6. Write `tests/test_storage.py` covering all state transitions.

**Phase 2 PR:**
1. Add `AgentGateway` protocol with `start_run(run_id, request) -> None`.
2. Add `LocalPipelineAgentGateway` and `FakeAgentGateway`.
3. Update `POST /runs` to return `{run_id, status: "queued"}` (HTTP 202).
4. Add `AGENT_BACKEND` setting.
5. Keep production on `AGENT_BACKEND=local`.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | OPEN (PLAN) | 16 issues, 3 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **UNRESOLVED:** 0 decisions unresolved
- **VERDICT:** ENG REVIEW OPEN — 3 critical gaps must be addressed before implementation (Firestore init failure handling, stale-run detector, IAM error handling in Phase 5)
