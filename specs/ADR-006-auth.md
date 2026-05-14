# ADR-006: Auth Strategy — Firebase Auth + Google OAuth

**Status:** Decided
**Date:** 2026-05-14

## Context

In v1, the product is likely used by a single founder (the builder) or a small circle of early testers. Auth adds friction. But without auth, there is no way to associate runs with users, enforce per-user quotas, or prepare for monetization.

Alternatives: no auth (open access), Firebase Auth with Google OAuth, Clerk, custom JWT, API key only.

## Decision

Use Firebase Auth with Google Sign-In (OAuth 2.0) as the sole auth method in v1.

## Rationale

- Firebase Auth is free for the usage levels this product will see in v1.
- Google Sign-In (one-click) is the lowest friction path for the target user, who almost certainly has a Google account.
- Firebase Auth integrates natively with Firestore security rules — run data can be scoped to the authenticated user's UID without custom backend auth logic.
- Keeps the stack Google-native and avoids adding a third-party auth vendor (Clerk, Auth0).

No auth was considered as the v1 option: valid if the product is a personal tool. Rejected because (a) Firestore needs a user UID to scope run storage anyway, and (b) building auth in later is more work than starting with it.

## What This Option Does NOT Do Well

- Google Sign-In only. Users without a Google account cannot use the product. This is acceptable for the target user in v1.
- Firebase Auth adds a dependency on Firebase SDK in the frontend. If the frontend is Streamlit, this requires a workaround (custom auth component or a separate login page).
- No built-in role-based access control. If you later need admin roles, you'll build it on top of Firebase Auth custom claims.

## Consequences

- Every API request to the Cloud Run backend must include a Firebase ID token in the Authorization header.
- The backend validates the ID token using Firebase Admin SDK on every request.
- Firestore security rules enforce that users can only read/write their own run documents.
- The Streamlit frontend requires a session state workaround for Firebase Auth (Streamlit's stateless model conflicts with OAuth flows). Consider a thin Flask login page that sets a session cookie if this becomes painful.
