# GapHunter

![GapHunter logo](assets/logo.svg)

GapHunter is an AI-assisted market gap research tool for founders. It takes a constraint prompt, researches job-market and competitor signals, and returns ranked startup idea briefs with adversarial critiques and a research coverage score.

The first implementation is a Cloud Run-ready FastAPI service. It runs in deterministic demo mode until Google API credentials are configured, which makes the app deployable and testable before Gemini, Google Custom Search, and Firestore are wired to real projects.

## Features

- Constraint parsing from natural language prompts
- Idea generation run endpoint and minimal browser UI
- Source-backed idea brief schema
- Adversarial critique and research coverage score fields
- Firestore-ready persistence boundary with in-memory fallback
- Dockerfile for Cloud Run
- GitHub Actions workflow for Cloud Run deployment
- MIT licensed

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## API

```bash
curl -X POST http://127.0.0.1:8000/runs \
  -H "content-type: application/json" \
  -d '{"prompt":"Swiss B2B workflows with digital inputs and high manual complexity"}'
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Configuration

All variables are optional for local demo mode.

| Variable | Purpose |
|---|---|
| `GCP_PROJECT_ID` | Google Cloud project used for Firestore and deployed runtime metadata |
| `FIRESTORE_COLLECTION` | Firestore collection for run results, default `runs` |
| `GEMINI_API_KEY` | Gemini API key for future live synthesis and critique |
| `GOOGLE_CUSTOM_SEARCH_API_KEY` | Google Custom Search API key for future live search |
| `JOB_SEARCH_ENGINE_ID` | Programmable Search Engine ID for job research |
| `COMPETITOR_SEARCH_ENGINE_ID` | Programmable Search Engine ID for competitor checks |

## GitHub Actions Deployment

The workflow at `.github/workflows/deploy.yml` builds a Docker image, pushes it to Artifact Registry, and deploys to Cloud Run.

Required repository variables:

- `GCP_PROJECT_ID`
- `GCP_REGION`, for example `europe-west6`
- `CLOUD_RUN_SERVICE`, for example `gaphunter`
- `ARTIFACT_REGISTRY_REPOSITORY`, for example `gaphunter`

Required repository secrets:

- Either `GCP_CREDENTIALS_JSON` for a deploy service-account JSON key
- Or both `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` for Workload Identity Federation

The target Google Cloud project must already have Cloud Run, Artifact Registry, IAM Credentials, Secret Manager, and Cloud Build APIs enabled.

## Documentation

- Product and architecture specs live in [`specs/`](specs/README.md).
- Wiki source lives in [`wiki/Home.md`](wiki/Home.md) and references the SVG logo.

## License

MIT. See [`LICENSE`](LICENSE).
