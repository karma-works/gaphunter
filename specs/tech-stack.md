# Tech Stack

## Summary

| Layer | Technology | Status | ADR |
|---|---|---|---|
| LLM | Gemini 2.0 Flash + Gemini 2.5 Pro | Recommended | ADR-003 |
| Agent framework | Google ADK (Python) | Recommended | ADR-002 |
| Web search | Google Custom Search API (Programmable Search Engine) | Recommended | ADR-004 |
| Runtime | Cloud Run (serverless) | Recommended | ADR-005 |
| Storage | Firestore | Recommended | ADR-001 |
| Auth | Firebase Auth + Google OAuth | Recommended | ADR-006 |
| Frontend (MVP) | Streamlit on Cloud Run | Recommended | — |
| Agent skills (coding context) | google/skills (gemini-api, cloud-run-basics, google-cloud-recipe-auth) | Recommended | — |
| Language | Python 3.12 | Recommended | — |

---

## Decided choices with rationale

### Google ADK (Python)
- Open source, code-first agent framework from Google
- Native Vertex AI deployment target, but runs locally and on Cloud Run without Vertex overhead
- Multi-agent support built in — important for the critique layer (separate sub-agent)
- Tool use / function calling is first-class
- Trade-off accepted: younger ecosystem than LangChain/LlamaIndex; some rough edges and API churn expected

### Gemini 2.0 Flash (research loops) + Gemini 2.5 Pro (synthesis + critique)
- Flash: fast and cheap. Suitable for the 15–30 search-and-extract iterations per run
- Pro: stronger reasoning for synthesis and adversarial critique. Worth the cost per run for the output that matters
- Trade-off accepted: two model calls per pipeline stage increases latency slightly; cost is manageable
- Do NOT use a single model for everything. Flash on critique will produce generic objections. Pro on every search loop is wasteful.

### Google Custom Search API
- Programmable Search Engine (PSE) scoped to specific job board domains (LinkedIn, Indeed, local boards) and startup/product directories (Product Hunt, Crunchbase, G2)
- 100 free queries/day; $5/1,000 after. Budget $0.10–$0.15 per full idea-generation run
- Trade-off accepted: not as powerful as a full browser automation scraper; some content behind auth will be missed. Acceptable for v1.

### Cloud Run
- Serverless. No idle cost. Pay per request. Appropriate for a tool that runs on-demand, not continuously.
- Easier ops than GKE. No cluster management.
- Trade-off accepted: cold start latency (1–3s) on first request. Acceptable for a tool where runs take 2–5 minutes anyway.

### Firestore
- Schemaless document store. Natural fit for storing idea-generation run results (each run is a document with nested idea briefs).
- No schema migrations to manage.
- Trade-off accepted: not good for relational queries. If you later need "all ideas that scored >80% across runs," you'll need to add indexes or move to BigQuery. Fine for v1.

---

## Open choices — recommendations

### Frontend
**Recommendation: Streamlit on Cloud Run**
- Main alternative: Flask/FastAPI with a custom React frontend
- Why Streamlit: v1 needs a working UI fast, not a beautiful one. Streamlit is Python-native and deploys to Cloud Run with almost no overhead. If the product gets traction, replace with a proper frontend later.
- Cost of Streamlit: harder to customize UX, no mobile support, streaming output requires workarounds. These are post-MVP problems.

### Auth
**Recommendation: Firebase Auth with Google OAuth**
- One-click Google Sign-In is appropriate for the target user (founders who likely have Google accounts)
- Firebase Auth is free for the usage levels this product will see in v1
- Main alternative: no auth at all for v1 (open access). Valid if you want faster launch and are running it as a personal tool first.

---

## What we explicitly chose NOT to use

| Technology | Reason |
|---|---|
| Vertex AI Agent Builder | Too opinionated and high-abstraction. Hides the pipeline, making debugging hard. ADK gives more control for the same Google-native deployment target. |
| LangChain / LlamaIndex | Not Google-native. Adds a heavy dependency for no clear benefit when ADK covers the use case. |
| GKE | Gross overkill for a stateless on-demand agent. Cloud Run is the right level. |
| BigQuery | Not needed for v1. Run logs don't need analytical queries yet. Firestore is enough. |
| Cloud SQL / AlloyDB | Relational database is wrong data model for variable-structure idea briefs. |
| OpenAI / Anthropic APIs | User constraint: Google services. Also: Gemini 2.5 Pro is competitive on reasoning tasks and keeps the stack coherent. |
| Browser automation (Playwright/Puppeteer) | Custom Search API is sufficient for v1. Browser automation adds operational complexity (headless Chrome on Cloud Run, anti-bot handling, maintenance burden). Add if Custom Search proves insufficient. |

---

## Agent skills to install (coding context)

These are SKILL.md context documents installed into Claude Code via:

```bash
npx skills add google/skills
```

Select at install time:
- `gemini-api` — Gemini API in Agent Platform (prompting, function calling, streaming)
- `cloud-run-basics` — deploying containerized Python to Cloud Run
- `google-cloud-recipe-auth` — Google Cloud authentication patterns (service accounts, ADC, OAuth)

These are NOT runtime agent tools. They are context documents that inform Claude Code when writing code against these services. Install them in the project repo, not in the agent runtime.
