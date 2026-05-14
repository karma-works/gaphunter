# ADR-007: GTM / MVP Scope — Personal Tool First, Then Productize

**Status:** Decided
**Date:** 2026-05-14

## Context

There are two common v1 launch postures for a tool like this:
1. **Product launch**: build a polished UI, payment flow, and onboarding; launch on Product Hunt; try to get paying users
2. **Personal tool first**: build it for yourself, use it to generate your own startup ideas, validate the output quality manually, then decide whether to productize

The core assumption of this product (see challenges.md, Challenge 4) has not been validated. Launching a paid product before validating the output quality is a high-risk move.

## Decision

Build and use it as a personal tool first. Do not build payment infrastructure in v1. Productize only after validating that the output produces ≥1 actionable startup lead.

## Rationale

- The output quality of the competitor check and critique layer is the entire value proposition. This cannot be assessed from the code — it requires running the agent on real constraints and evaluating the output manually.
- Building a payment flow before validating output quality wastes time on infrastructure that may not be needed.
- "Use it yourself" is the fastest feedback loop. The builder is also the primary user archetype.
- Productization (payment, onboarding, public domain, SaaS features) is a distinct phase and belongs in Phase 1, not Phase 0.

## What This Option Does NOT Do Well

- No revenue in Phase 0. This is a time-and-cost investment with no financial return until Phase 1.
- Slower path to market. If a competitor launches a similar product in the Phase 0 window, you're behind.
- "Personal tool" often stays personal. Without a forcing function (paying users, deadline), productization can stall.

## Consequences

- Phase 0 success criterion: the agent returns ≥2 ideas that the builder considers genuinely interesting and gap-confirmed, on the first 3 constraint sets tried.
- Phase 1 begins only after that criterion is met.
- No Stripe, no payment UI, no public landing page in Phase 0.
- Auth is still included (Firebase Auth) because it's needed for Firestore scoping, not for paywalling.
