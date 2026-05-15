# Agent Engine Operations

## Phase 4 Spike Status

Last checked: 2026-05-15

The Phase 4 Agent Engine spike has started but is not complete. The project is configured for
the spike, but deployment is blocked until Application Default Credentials are available locally
and the Reasoning Engine service agent is granted Firestore write access.

## Verified Project State

- Project ID: `gaphunter-496315`
- Project number: `519220506089`
- Active `gcloud` account: `chris.haegele@gmail.com`
- Vertex AI API: enabled during the spike
- Vertex AI service identity: generated during the spike

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

## Blockers

### Application Default Credentials

No local `application_default_credentials.json` file was present under the Cloud SDK config.
The Agent Platform Python SDK uses ADC, so local deployment cannot proceed until ADC is
configured.

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
agent must receive `roles/datastore.user` on the project:

```bash
gcloud projects add-iam-policy-binding gaphunter-496315 \
  --member=serviceAccount:service-519220506089@gcp-sa-aiplatform-re.iam.gserviceaccount.com \
  --role=roles/datastore.user \
  --condition=None
```

This is a persistent project-level IAM change and should be approved explicitly before running.

## Deployment Approach

Use inline source deployment for the first hello-world spike. Google documentation currently
supports deploying from local source files with `client.agent_engines.create` using:

- `source_packages`
- `entrypoint_module`
- `entrypoint_object`
- `class_methods`
- optional `requirements_file`

For the first deployable spike, keep the source package minimal and expose a single method
that returns a deterministic response. Only after this deploy/invoke path works should the
repo add the `agent/` package and Firestore-writing orchestrator.

## Shared Schema Strategy

When Phase 4 proceeds past the spike gate, use `app.models` as the shared schema package for
the initial Agent Engine implementation. This keeps Cloud Run and Agent Engine validating
against the exact same `RunResult`, `RunStatusResponse`, `ProgressEvent`, and `SourceEvidence`
models. Revisit a dedicated `gaphunter_models` package only if deployment packaging or import
boundaries become a real problem.

## Local Development Loop

Until Agent Engine deployment is verified, local orchestration development should use:

```bash
AGENT_BACKEND=local pytest -q
AGENT_BACKEND=fake pytest -q
```

The `FakeAgentGateway` exercises the queued/running/completed/failed Firestore contract without
network or Google credentials. For Phase 6 agent work, add tests that call the orchestrator
directly with fake Gemini and fake search clients before deploying to Agent Engine.
