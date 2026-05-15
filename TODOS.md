# TODOS

## TODO-001: Event ordering model for Firestore progress events

**Status:** Resolved for Phase 1.

**Decision:** Use a per-run monotonic sequence counter and zero-padded event document IDs
(`000001`, `000002`, ...). Public responses return events in that sequence order.

**What:** Define how `events/{event_id}` are ordered in the `runs/{run_id}/events` subcollection.

**Why:** Random UUIDs as event IDs make ordering dependent on Firestore server timestamps, which can produce inconsistent ordering when events are written within the same millisecond. The UI polling endpoint (Phase 3) and refinement chat (Phase 8) both rely on deterministic event ordering.

**Pros:** Deterministic ordering prevents subtle UI bugs where progress events render out of sequence during Agent Engine runs with parallel stage writes.

**Cons:** Requires a monotonic counter or structured ID scheme (e.g., `{unix_ms}_{seq}` or `server_timestamp`-ordered queries) — minor upfront design work.

**Context:** Resolve in Phase 1 Firestore contract design before any event collection code is written. Options: monotonic sequence number on the run document + event ID = `f"{seq:06d}"`, or rely on Firestore server timestamp queries with `order_by("created_at")`.

**Depends on:** Phase 1 (Firestore Run Contract)

---

## TODO-002: Local developer loop for Agent Engine

**What:** Define and document how to run and test the Agent Engine orchestrator locally without deploying to `gaphunter-496315`.

**Why:** Phase 6 develops 8 agents across 3 sub-phases. Without a local loop, every iteration requires a full Cloud deployment, slowing feedback to minutes per cycle instead of seconds.

**Pros:** 10x faster Phase 6 iteration. Enables CI tests for agent orchestration logic without GCP credentials.

**Cons:** Requires a Firestore emulator setup and fake Gemini/Brave Search clients. ~2-4 hours of tooling work.

**Context:** Resolve in Phase 4 alongside the Agent Engine scaffold. At minimum, verify that `AGENT_BACKEND=local` with a Firestore emulator (`gcloud beta emulators firestore start`) and `FakeAgentGateway` covers the Phase 6 development workflow. Document in `README.md` or `specs/agent-engine-operations.md`.

**Depends on:** Phase 4 (Agent Engine Scaffold), Phase 2 (FakeAgentGateway)
