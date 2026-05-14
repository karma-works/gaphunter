# ADR-001: Data Storage — Firestore

**Status:** Decided
**Date:** 2026-05-14

## Context

The agent produces structured run outputs: each run has metadata (constraints, timestamp, user) and a variable-length list of idea briefs (each with job description, competitor check result, critique, score). The structure varies per run. We need somewhere to persist runs so users can review past output. No relational queries needed in v1.

Alternatives considered: Cloud SQL (PostgreSQL), BigQuery, Cloud Storage (JSON files), Firestore.

## Decision

Use Firestore (Native mode) as the primary data store for run results and user data.

## Rationale

- The data is naturally document-shaped. A run maps directly to a Firestore document with a nested array of idea briefs. No schema migrations needed as the idea brief format evolves.
- Firestore's free tier (1 GiB storage, 50K reads/day, 20K writes/day) covers the entire v1 usage period.
- Firestore integrates natively with Firebase Auth, simplifying user-scoped queries.
- Reads and writes are fast for the small document sizes involved.

## What This Option Does NOT Do Well

- Analytics queries across runs (e.g., "which industries produce the most ideas over time") require full collection scans or secondary indexes. At scale this gets expensive. BigQuery export is the standard escape hatch.
- Complex relational queries are not possible. If the data model needs joins, this is the wrong choice.

## Consequences

- Run output must be serializable to JSON (no binary blobs, no ORM objects).
- Design the Firestore document schema upfront — Firestore doesn't enforce it but the application code must be consistent.
- If analytics become important post-MVP, set up a BigQuery export pipeline.
