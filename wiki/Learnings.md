# Learnings

This page records implementation and vendor learnings for GapHunter. Add new dated entries here when a product, API, deployment, or research assumption changes.

## 2026-05-14: Google Search Providers

### Custom Search JSON API

Source: [Custom Search JSON API overview](https://developers.google.com/custom-search/v1/overview)

Key findings:

- Custom Search JSON API can return JSON search results from a configured Programmable Search Engine, but it requires both an API key and a search engine ID.
- Google documents the API as closed to new customers.
- Existing customers have until January 1, 2027 to transition to an alternative solution.
- Published legacy pricing is 100 free queries per day, then $5 per 1,000 queries up to 10,000 queries per day.
- Service account authentication is not a practical workaround for GapHunter's current Custom Search integration. The JSON API path is API-key based, and our tests with project-level enablement plus API keys still returned access-denied responses for the project.

Project implication:

Custom Search JSON API should not be treated as GapHunter's durable live-web research backend. Keep the adapter as a compatibility path for accounts that already have API access, but design the search boundary so another provider can be swapped in.

### Vertex AI Search / Agent Search

Sources:

- [Migrate from Custom Search Site Restricted JSON API](https://docs.cloud.google.com/generative-ai-app-builder/docs/migrate-from-cse)
- [Agent Search pricing](https://cloud.google.com/generative-ai-app-builder/pricing)

Key findings:

- Google is renaming Vertex AI Search to Agent Search in current documentation.
- Agent Search is Google's recommended path for site-restricted search, not a drop-in live open-web replacement.
- Website search requires creating an Agent Search app and website data store, then configuring URL patterns to index.
- Website search uses Enterprise edition features.
- Advanced website indexing and richer generated answers can require domain verification and add indexing costs.
- Authentication differs by API path:
  - `searchLite` can use an API key.
  - `search` and `answer` use OAuth 2.0 and appropriate Discovery Engine IAM roles.
- General pricing currently includes a 10,000 query per account per month free trial, then $1.50 per 1,000 Standard search queries or $4.00 per 1,000 Enterprise search queries. Advanced generative answers add $4.00 per 1,000 user input queries.
- Index storage has a 10 GiB monthly free quota. Above that, listed storage pricing is based on indexed raw data. For website data stores, Google estimates storage as 500 KiB per indexed page, with a 1,000-page website example at about $2.38 per month before free quota effects.

Project implication:

Agent Search can work if GapHunter narrows research to curated source lists such as specific job boards, review sites, competitor directories, and domain allowlists. It is weaker for broad discovery across the open web because the system must first know what sites to index. Runtime query latency should be suitable for product use after indexing, but setup, indexing freshness, source coverage, and cost monitoring become part of the product architecture.

Decision guidance:

- Use Agent Search if Google-native infrastructure, controlled source coverage, IAM, and indexed-site quality matter more than open-web breadth.
- Use another web search provider if GapHunter needs broad web discovery, faster MVP setup, or lower operational complexity.
- Keep provider-specific details behind a search adapter so Custom Search, Agent Search, and non-Google search providers can coexist during evaluation.
