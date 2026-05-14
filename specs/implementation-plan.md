# Implementation Plan

## Phase 0 — Build and validate the personal tool (6–8 weeks)

Success criterion: agent returns ≥2 compelling, gap-confirmed ideas on 3 different constraint sets. If this is not achieved, stop and reassess the hypothesis before continuing.

### Week 1 — Infrastructure and scaffolding

- [ ] Create Google Cloud project, enable billing
- [ ] Enable APIs: Gemini API, Firestore, Firebase Auth, Secret Manager, Cloud Run, Cloud Build
- [ ] Create Brave Search API key for live web research
- [ ] Create service account with least-privilege IAM roles (Firestore read/write, Secret Manager accessor)
- [ ] Set up Secret Manager with: Gemini API key, Brave Search API key, Firebase project credentials
- [ ] Initialize Python project: `uv` for package management, `pyproject.toml`, `Dockerfile`
- [ ] Install ADK: `pip install google-adk`
- [ ] Install Google agent skills: `npx skills add google/skills` → select `gemini-api`, `cloud-run-basics`, `google-cloud-recipe-auth`
- [ ] Verify: call Gemini 2.0 Flash with a test prompt; call Brave Search API with a test query; confirm results

### Week 2 — Core research pipeline

- [ ] Implement `search_tool` ADK tool: wraps Brave Search API, returns list of `{title, snippet, url}` results
- [ ] Implement `job_research_agent`: ADK Agent using Gemini 2.0 Flash, takes constraint parameters, generates search queries, calls `search_tool`, extracts structured job descriptions
- [ ] Define `JobCandidate` Pydantic model: `{title, description, industry, source_url, estimated_salary_band, io_type, complexity_signal}`
- [ ] Implement constraint filter: drop any `JobCandidate` without a `source_url` (hard requirement from challenges.md, Challenge 11)
- [ ] Implement constraint parser: takes natural language user input, extracts structured constraint fields (geography, industry, exclusions, complexity threshold)
- [ ] Write unit tests with mocked search responses for the filter and parser logic

### Week 3 — Competitor check pipeline

- [ ] Implement `competitor_check_agent`: ADK Agent using Gemini 2.0 Flash, takes a `JobCandidate`, generates 3–5 search queries targeting "AI agent for [job type]"
- [ ] Define `CompetitorCheckResult` model: `{job_title, competitors_found: list[{name, url, description}], gap_confirmed: bool, coverage_note: str}`
- [ ] `coverage_note` must always be present: "Checked public web results via Brave Search as of [date]. Non-indexed and stealth products not covered."
- [ ] Implement deduplication: if two `JobCandidate` items map to the same competitor check result, merge them
- [ ] Write tests: verify competitor check correctly identifies a known product (e.g., search for "AI agent for expense reporting" should return Brex/Ramp/similar)

### Week 4 — Synthesis and critique pipeline

- [ ] Implement `idea_synthesis_agent`: ADK Agent using Gemini 2.5 Pro, takes a list of gap-confirmed `JobCandidate` + `CompetitorCheckResult` pairs, generates `IdeaBrief` objects
- [ ] Define `IdeaBrief` model: `{title, one_liner, target_customer, job_being_replaced, gap_evidence: list[str], source_urls: list[str], ai_feasibility_note: str}`
- [ ] Implement `critique_agent`: separate ADK Agent using Gemini 2.5 Pro, takes an `IdeaBrief`, returns `Critique` with ≥2 specific objections, each grounded in data from the brief (not generic)
- [ ] Implement `scorer`: takes `IdeaBrief` + `Critique`, returns `score: float` (0–1) and `score_rationale: str`. Name it "research coverage score" not "confidence score" (see challenges.md, Challenge 8)
- [ ] Prompt engineering: iterate critique prompts until objections are specific and data-grounded, not generic. Test with ≥5 manually-constructed briefs.

### Week 5 — Orchestrator and storage

- [ ] Implement `IdeaGenerationOrchestrator`: ADK root agent that chains all sub-agents: constraint parsing → job research → competitor check → synthesis → critique → scoring → ranked output
- [ ] Define `RunResult` Firestore document schema: `{user_id, created_at, constraints: dict, ideas: list[IdeaBrief+Critique+Score], run_duration_s: float}`
- [ ] Implement Firestore persistence: save each `RunResult` after completion; read back by run ID
- [ ] Implement basic error handling: if a search call fails, log and continue (don't abort the whole run); flag missing data in output
- [ ] Write integration test: run the full pipeline on one constraint set against real APIs (expect this to take a few iterations to get right)

### Week 6 — Frontend and deployment

- [ ] Build minimal Streamlit UI: constraint input form, run trigger button, progress indicator (polling), results display (ranked briefs with expand/collapse per idea)
- [ ] Results display must show: idea title, one-liner, job being replaced, gap evidence list, source URLs, critique objections, research coverage score
- [ ] Implement Firebase Auth in Streamlit: Google Sign-In → Firebase ID token → passed to backend API
- [ ] Build minimal Flask API layer: `POST /runs` (start a run, return run ID), `GET /runs/{id}` (return run result when complete)
- [ ] Write Dockerfile: Python 3.12, install dependencies, run Flask app
- [ ] Deploy to Cloud Run via Cloud Build: `gcloud run deploy`
- [ ] Set all secrets via Secret Manager environment variable references (not hardcoded)
- [ ] Smoke test: run one full constraint set end-to-end on the deployed service

### Week 7–8 — Validation and iteration

- [ ] Run the agent on ≥5 different constraint sets (Swiss market, other geographies, different industries)
- [ ] Manually evaluate every output: is the job real (verify source URL)? Is the competitor check credible? Are the critique objections specific?
- [ ] Track: what % of ideas pass manual quality review?
- [ ] Fix the 3 worst-performing pipeline stages based on evaluation
- [ ] Decision point: if ≥70% of ideas pass manual quality review → Phase 0 success, proceed to Phase 1. If not → iterate on prompts/pipeline before Phase 1.

---

## Phase 1 — Productize (outline only, ~8–12 weeks after Phase 0 success)

- Public landing page and signup flow
- Stripe integration: pay-per-run (CHF 30–50) or subscription (CHF 120/month)
- Onboarding: guided constraint form with examples, output walkthrough
- Deep-dive flow (Flow 2 from product.md)
- Constraint iteration / session memory
- Run history and saved briefs
- Improved frontend (replace Streamlit with proper React UI or keep Streamlit but style it)
- Rate limiting and abuse prevention
- Geography-specific regulatory awareness layer

---

## Phase 2 — Scale (outline only, post Phase 1 traction)

- API output (JSON) for external integrations
- Outcome feedback loop: thumbs up/down on ideas, track which were acted on
- Multi-language output (German, French for Swiss/DACH market)
- Idea clustering across runs
- B2B licensing to accelerators / VC analysts / innovation consultancies
- Model fine-tuning or few-shot optimization based on outcome data
