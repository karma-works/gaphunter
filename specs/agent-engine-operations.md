# Agent Engine Operations

## Phase 5 Status

`AgentEngineGateway` is implemented in `app/agent_gateway.py`. Set the following env vars to
enable it on Cloud Run:

```bash
AGENT_BACKEND=agent_engine
AGENT_ENGINE_RESOURCE_NAME=projects/519220506089/locations/us-central1/reasoningEngines/119587832439242752
MAX_SEARCH_QUERIES_PER_RUN=20   # cost kill switch — abort if exceeded
MAX_GEMINI_CALLS_PER_RUN=50     # cost kill switch — abort if exceeded
```

The gateway fires a daemon thread and returns immediately. The Agent Engine orchestrator
writes all state transitions directly to Firestore. Set `AGENT_BACKEND=local` to roll back
to the synchronous in-process pipeline.

Cloud Run needs `roles/aiplatform.user` on the project to invoke Agent Engine. Verify before
switching `AGENT_BACKEND=agent_engine` in production.

## Phase 4 Spike Status

Last checked: 2026-05-15

The Phase 4 Agent Engine spike passed. A deterministic Agent Engine was deployed, invoked, and
verified to write a completed `RunResult` plus a progress event to Firestore.

## Verified Project State

- Project ID: `gaphunter-496315`
- Project number: `519220506089`
- Active `gcloud` account: `chris.haegele@gmail.com`
- Vertex AI API: enabled during the spike
- Vertex AI service identity: generated during the spike
- Reasoning Engine service agent Firestore role: granted `roles/datastore.user`
- Agent Engine staging bucket: `gs://gaphunter-agent-engine-staging-519220506089`
- Deployed spike resource:
  `projects/519220506089/locations/us-central1/reasoningEngines/119587832439242752`
- Firestore verification run: `22a6082278404eaa8a57dec7778fc2ef`

Enabled services observed before enabling Vertex AI included:

- `cloudbuild.googleapis.com`
- `cloudtrace.googleapis.com`
- `datastore.googleapis.com`
- `firestore.googleapis.com`
- `iam.googleapis.com`
- `logging.googleapis.com`
- `monitoring.googleapis.com`
- `run.googleapis.com`
- `secretmanager.googleapis.com`
- `serviceusage.googleapis.com`
- `storage.googleapis.com`
- `telemetry.googleapis.com`

## Completed Setup

### Application Default Credentials

The Agent Platform Python SDK uses ADC. For this environment, ADC was configured under:

```text
/tmp/gcloud-config/application_default_credentials.json
```

The quota project is `gaphunter-496315`.

To refresh these credentials if they expire, run:

Run:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project gaphunter-496315
```

In this sandbox, use a writable Cloud SDK config directory:

```bash
export CLOUDSDK_CONFIG=/tmp/gcloud-config
```

### Firestore IAM Grant

Phase 4 requires Agent Engine to write directly to Firestore. The Reasoning Engine service
agent received `roles/datastore.user` on the project:

```bash
gcloud projects add-iam-policy-binding gaphunter-496315 \
  --member=serviceAccount:service-519220506089@gcp-sa-aiplatform-re.iam.gserviceaccount.com \
  --role=roles/datastore.user \
  --condition=None
```

## Deployment Approach

The installed `google-cloud-aiplatform==1.153.1` SDK exposes the object deployment API:

```python
import vertexai
from vertexai import agent_engines

vertexai.init(project=..., location=..., staging_bucket=...)
agent_engines.create(root_agent, requirements=..., extra_packages=...)
```

The docs also describe newer inline source deployment via `vertexai.Client(...).agent_engines`,
but that API was not available in the installed SDK. The successful spike used object deployment
with `extra_packages=["agent"]`.

Do not include the top-level Cloud Run `app` package in `extra_packages` with this legacy path:
it shadows Agent Runtime's internal `/code/app` package and causes startup failures.

## Shared Schema Strategy

For local tests, `agent.orchestrator` validates deterministic output with `app.models`.
For deployed runtime, the agent package is self-contained and writes schema-compatible Firestore
documents directly to avoid the `app` package name collision described above.

Before Phase 6 writes more complex outputs, consider extracting `app.models` into a neutral
package such as `gaphunter_models` so Cloud Run and Agent Engine can import shared models
without colliding with Agent Runtime internals.

## Local Development Loop

Until Agent Engine deployment is verified, local orchestration development should use:

```bash
AGENT_BACKEND=local pytest -q
AGENT_BACKEND=fake pytest -q
```

The `FakeAgentGateway` exercises the queued/running/completed/failed Firestore contract without
network or Google credentials. For Phase 6 agent work, add tests that call the orchestrator
directly with fake Gemini and fake search clients before deploying to Agent Engine.
