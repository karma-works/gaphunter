# Challenges

## Challenge 1: Competitor gap detection is unreliable at scale

**Assumption:** Web search can reliably confirm whether a specific AI agent product already exists for a given job type.

**Most likely failure mode:** The agent misses a relevant competitor because the competitor uses different language, is not indexed on Product Hunt/Crunchbase, or is a feature of a larger platform rather than a standalone product. Founders act on a "no competitor" signal that is false.

**Failure consequence:** User builds in a direction that's already saturated. This is a credibility-destroying failure — if it happens once, the user never trusts the tool again.

**Counter-evidence strength:** Strong. Search-based competitor discovery has known blind spots: non-English products, internal enterprise tools, stealth startups, and large-platform features (e.g., a Salesforce module that does exactly what you're building). No search strategy fully covers these.

**Mitigation:** Be explicit about what the competitor check covers and what it misses. Frame output as "no obvious public competitor found" not "no competitor exists." Encourage users to do a 30-minute manual check before committing. Do not oversell this feature.

---

## Challenge 2: Job complexity scoring is subjective and hard to automate

**Assumption:** The agent can reliably classify whether a job is "complex enough" to be a moat-worthy AI agent.

**Most likely failure mode:** Complexity is contextual. "Complex" for a Swiss regulatory context may be trivial in a US market. The agent either over-filters (misses valid ideas) or under-filters (returns jobs that any GPT wrapper can do, with no moat).

**Failure consequence:** Output is either too thin (3 ideas, all weak) or too crowded (10 ideas that are just "ChatGPT for X").

**Counter-evidence strength:** Medium. Proxy signals exist (salary data, years of experience required, certification requirements) but they're imperfect.

**Mitigation:** Let users define complexity thresholds in their constraints explicitly. Also use salary band as a proxy — higher-paid jobs are likely more complex and have higher WTP.

---

## Challenge 3: Google Search API rate limits and cost will spike on real runs

**Assumption:** Running 10–20 search queries per idea generation run is cheap and fast enough for a good UX.

**Most likely failure mode:** Each run requires 15–30 searches (job research + competitor checks per candidate). Google Custom Search API costs $5 per 1,000 queries. A single run costs $0.10–$0.15 in search API calls alone. At scale, this compounds. Latency per run could be 3–8 minutes.

**Failure consequence:** Margins collapse if the product is priced as pay-per-run at low price points. UX suffers if latency is too high for interactive use.

**Counter-evidence strength:** Medium. This is a known cost driver, not a speculation.

**Mitigation:** Batch searches efficiently, cache results aggressively (same job type searched twice → reuse). Set realistic per-run cost floor when pricing. Consider async runs with email/webhook delivery rather than synchronous wait.

---

## Challenge 4: The "purely digital I/O" filter eliminates most interesting ideas

**Assumption:** There's a large enough set of complex, digital-I/O, non-tax jobs with no AI agent competitor.

**Most likely failure mode:** The intersection of (complex + digital I/O + no competitor + not tax/legal/accounting) is very small. The agent runs and returns 1–2 ideas, or returns ideas that are too niche to be businesses.

**Failure consequence:** Product feels useless. User's constraints are too narrow for the agent to find anything real.

**Counter-evidence strength:** Medium. This is the core value hypothesis and it has not been tested. It is an assumption, not a known fact.

**Mitigation:** Build constraint relaxation into the agent — if no results pass strict filters, progressively loosen and flag which constraint was relaxed. Also: test the constraint manually before building. Spend 2 hours trying to find 5 ideas that fit the criteria by hand. If you can't do it manually, the agent can't either.

---

## Challenge 5: Adversarial critique is only as good as the model's training data

**Assumption:** The LLM can generate genuinely sharp critiques that a founder wouldn't think of themselves.

**Most likely failure mode:** The critique layer generates plausible-sounding but generic objections ("market may be small", "regulation could be a risk") that don't actually stress-test the specific idea. Founders learn to ignore the critique because it's always the same 3 objections.

**Failure consequence:** The differentiating feature of the product becomes a checkbox that adds no value. The product is just a fancy web scraper.

**Counter-evidence strength:** Medium. LLM critique quality is highly variable depending on prompt engineering. Needs significant iteration to get non-generic output.

**Mitigation:** Critique must be grounded in data returned from research, not generic. Prompt engineering should force the model to cite specific evidence for each objection. Evaluate critique quality manually on a test set before shipping.

---

## Challenge 6: Swiss market is too small to validate anything

**Assumption:** Switzerland is a useful launch market that provides signal about product-market fit.

**Most likely failure mode:** Switzerland has ~8M people, limited startup ecosystem, and language fragmentation (DE/FR/IT). A product that works for Switzerland may not generalize. If you optimize for Swiss constraints, you build a niche tool. If you ignore them, you lose the specificity that makes the output valuable.

**Failure consequence:** Either you build a Swiss-specific product with a tiny TAM, or you build generic and lose the example-driven value.

**Counter-evidence strength:** Medium.

**Mitigation:** Switzerland is fine as a *test* market — use it to validate the mechanics. Don't position it as the end market. Build geography as a parameter, not a hardcode.

---

## Challenge 7: Users won't know how to write good constraints

**Assumption:** Users can write effective constraint prompts that give the agent enough direction to find good ideas.

**Most likely failure mode:** Users write vague constraints ("something in healthcare") or over-constrained prompts ("B2B SaaS for Swiss SMEs in German-speaking cantons doing ISO compliance for manufacturing companies"). The agent either returns nothing useful or returns ideas that don't fit what the user actually wanted.

**Failure consequence:** Bad output, user blames the product, churn after first run.

**Counter-evidence strength:** Medium. Prompt quality variance is a real UX problem for all LLM-powered products.

**Mitigation:** Provide 3–5 worked example constraint prompts. Guide users through a structured constraint form as an alternative to free-text. Show what constraints produced good output vs. bad output.

---

## Challenge 8: The output is research, not validation — founders may confuse them

**Assumption:** Founders understand that "high gap confidence" means the research didn't find a competitor, not that the idea will succeed.

**Most likely failure mode:** A founder sees a 90% confidence score, builds for 6 months, launches, and finds the market doesn't exist — then blames the product. The agent found a gap in the market, not a market in the gap.

**Failure consequence:** Reputational damage when users conflate research quality with business success probability.

**Counter-evidence strength:** Strong. This confusion is universal and predictable.

**Mitigation:** Be extremely explicit in every output: confidence scores measure research coverage, not business viability. Include a mandatory disclaimer section in each brief. Consider renaming "confidence score" to "research coverage score" to be less misleading.

---

## Challenge 9: Google services dependency creates lock-in and cost risk

**Assumption:** Google Custom Search + Vertex AI + Gemini is the right foundation and will remain cost-stable and available.

**Most likely failure mode:** Google deprecates or reprices a service (it happens), or rate limits hit during a peak usage period. Also: Vertex AI/Gemini is not the cheapest or fastest option for all tasks in the pipeline.

**Failure consequence:** Infrastructure disruption at a critical moment. Cost spikes that break unit economics.

**Counter-evidence strength:** Medium. Google has deprecated services before (Google+, various APIs). Gemini is new enough that pricing is not guaranteed stable.

**Mitigation:** Abstract the LLM and search layers behind interfaces so they can be swapped. Don't tightly couple to specific Google API surfaces unless there's a concrete capability reason.

---

## Challenge 10: Agent skills from google/genai-toolbox may not match the task

**Assumption:** The skills/tools from https://github.com/googleapis/genai-toolbox (likely the correct repo) are relevant and production-quality for this use case.

**Most likely failure mode:** The repo has tools for database access and structured data, not for web research or job market analysis. You spend time integrating tools that don't actually help, or find they're at an early maturity level.

**Failure consequence:** Wasted integration effort. Agent is rebuilt around different tooling after the fact.

**Counter-evidence strength:** Medium. The actual capabilities of that repo need to be verified before assuming fit.

**Mitigation:** Read the repo before committing to it. Verify which tools are available and whether they cover web search, data extraction, and structured output for this use case. Don't assume fit from the name.

---

## Challenge 11: Hallucination in job research output

**Assumption:** The agent returns real, existing jobs — not plausible-sounding but fictitious roles.

**Most likely failure mode:** When job board searches return sparse results, the LLM fills in gaps with plausible job descriptions it synthesizes from training data. User gets "Research Analyst, Federal Procurement Office" which sounds real but doesn't correspond to an actual data source.

**Failure consequence:** User validates an AI-hallucinated market. This is worse than no output.

**Counter-evidence strength:** Strong. This is a known failure mode of LLM-powered research agents.

**Mitigation:** Every job in the output must be traceable to a source URL. If no URL, it doesn't appear in output. This is a hard constraint, not a "nice to have."

---

## Challenge 12: No feedback loop — the agent can't learn what worked

**Assumption:** The agent produces useful output without knowing which ideas actually became successful businesses.

**Most likely failure mode:** The agent optimizes for research coverage, not for business outcomes. Without outcome feedback, it can't improve its scoring model over time. Over 12 months, the quality stagnates.

**Failure consequence:** Product doesn't get smarter. Competitors who build feedback loops overtake it.

**Counter-evidence strength:** Weak in v1 — there's no data to learn from yet. Becomes strong in v2.

**Mitigation:** Design the data model to capture which ideas were acted on, which were dismissed, and eventually whether they succeeded. Even a simple thumbs-up/down is enough to start. Don't build the learning loop in v1, but don't make it impossible to add.

---

## Verbal summary

**The 3 biggest risks:**

1. **Competitor check false negatives (Challenge 1)** — This is the most trust-destroying failure. If you tell a founder "no competitor exists" and they build for 6 months and find one, the product has done active harm. Mitigate by being explicit about coverage limits and encouraging manual spot-checks.

2. **The constraint intersection may be empty (Challenge 4)** — The core value hypothesis (there are multiple complex, digital-I/O, uncrowded AI agent opportunities) has not been tested. You need to validate this manually *before* building the agent, not after.

3. **Output is confused with validation (Challenge 8)** — Founders will treat a high confidence score as a green light to build. This is a misuse that is entirely predictable. The framing and naming of scores must be designed to resist this from day one.

**The assumption that kills the project if wrong:**

Challenge 4 is the existential one. If the intersection of (complex + digital I/O + not crowded + not excluded) is genuinely thin, the agent finds nothing worth building and the product has no value. Test this manually before writing code.

**What to validate before writing any code:**

Spend 4 hours manually doing what the agent would do. Take the Swiss example constraint. Search job boards. Pick 5 candidates. Check competitors for each. See if you end up with ≥2 ideas that feel genuinely interesting and gap-confirmed. If yes, the agent is worth building. If no, the constraints need rethinking first.
