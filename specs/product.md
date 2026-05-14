# Product

## User types

| User | Goal | Trust level |
|---|---|---|
| Founder (primary) | Get validated startup idea leads | Full access |
| API consumer (future) | Integrate idea output into their own tooling | Scoped API key |

## Core flows

### Flow 1: Idea generation run

1. User submits a constraint prompt (natural language or structured JSON): geography, industry, exclusions, complexity level, I/O type preference.
2. Agent parses constraints and extracts search parameters.
3. Agent runs web research: searches job boards (LinkedIn, Indeed, local boards), professional association sites, and government labor statistics for matching job types.
4. Agent filters results against constraints (digital I/O, complexity threshold, excluded categories).
5. Agent checks each candidate job for existing AI-agent competitors: searches product directories (Product Hunt, G2, Crunchbase), startup lists, and Google search.
6. Agent generates 3–5 business idea briefs from filtered, gap-confirmed job types.
7. Agent runs adversarial critique on each brief: attempts to find the fatal flaw, weak assumption, or obvious reason it won't work.
8. Agent scores each idea on: gap confidence, technical feasibility, market size signal, critique severity.
9. Agent outputs ranked briefs in structured format (markdown or JSON).

### Flow 2: Idea deep-dive

1. User selects one brief from a prior run and asks for deeper research.
2. Agent expands competitor research (more sources, funding data, product reviews).
3. Agent researches willingness-to-pay signals (job salary data, existing service pricing, outsourcing rates).
4. Agent identifies the 3 most dangerous assumptions and suggests how to validate each.
5. Agent outputs an expanded brief with validation roadmap.

### Flow 3: Constraint iteration

1. User reviews output and adjusts constraints ("exclude fintech too", "focus on B2B only", "make it more niche").
2. Agent reruns from step 3 of Flow 1 with updated parameters.
3. Output is a new ranked list, not a modification of the old one (clean slate per run).

## Feature list

| Feature | User | MVP | Post-MVP | Notes |
|---|---|---|---|---|
| Natural language constraint parsing | Founder | Yes | — | Must handle ambiguity gracefully |
| Job/role web research (Google Search, job boards) | Founder | Yes | — | Core value driver |
| Competitor gap check | Founder | Yes | — | Must return named competitors or explicit "none found" |
| Adversarial critique layer | Founder | Yes | — | Self-critique is the differentiator |
| Confidence scoring per idea | Founder | Yes | — | Numeric + rationale |
| Structured markdown output | Founder | Yes | — | Easy to read and copy |
| Deep-dive flow | Founder | No | Yes | Adds WTP research |
| JSON / API output | API consumer | No | Yes | |
| Constraint iteration / session memory | Founder | No | Yes | |
| Saved runs / history | Founder | No | Yes | |
| Geography-specific regulatory check | Founder | No | Yes | E.g., Swiss data protection, sector restrictions |
| Multi-language output | Founder | No | Yes | German/French for Swiss market |
| Idea clustering / deduplication across runs | Founder | No | Yes | |

## Monetization hypothesis

**Assumption (unproven):** Founders will pay for a tool that saves 10–20 hours of manual research per idea cycle.

Likely models:
- **Pay-per-run**: CHF 20–50 per full idea generation run. Low friction, no commitment. Test first.
- **Subscription**: CHF 100–200/month for unlimited runs. Makes sense once a user validates the output quality.
- **B2B license**: Sell to accelerators, VCs, or innovation consultancies who run it repeatedly. Higher ACV, longer sales cycle.

What is NOT proven: whether the output quality is high enough that users trust it enough to pay. That is the only thing that matters before monetization is relevant.
