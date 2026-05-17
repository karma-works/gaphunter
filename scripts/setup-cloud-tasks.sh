#!/usr/bin/env bash
# Setup Cloud Tasks queue and IAM for GapHunter Agent Engine invocation.
#
# Run once per project before switching AGENT_BACKEND=agent_engine.
# After verifying task delivery is reliable, remove --min-instances 1 from
# the Cloud Run deployment to allow scale-to-zero.
#
# Usage:
#   GCP_PROJECT_ID=gaphunter-496315 ./scripts/setup-cloud-tasks.sh
#
# Optional overrides (exported before running):
#   CLOUD_TASKS_REGION   default: us-central1
#   CLOUD_TASKS_QUEUE_NAME  default: gaphunter-agent-engine
#   CLOUD_RUN_SERVICE    default: gaphunter
#   CLOUD_TASKS_SA_NAME  default: cloud-tasks-invoker

set -euo pipefail

PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID must be set}"
REGION="${CLOUD_TASKS_REGION:-us-central1}"
QUEUE_NAME="${CLOUD_TASKS_QUEUE_NAME:-gaphunter-agent-engine}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-gaphunter}"
SA_NAME="${CLOUD_TASKS_SA_NAME:-cloud-tasks-invoker}"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
QUEUE_PATH="projects/${PROJECT}/locations/${REGION}/queues/${QUEUE_NAME}"

echo "==> Creating service account ${SA_EMAIL} ..."
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="Cloud Tasks → Cloud Run invoker" \
  --project="${PROJECT}" 2>/dev/null \
  || echo "    (already exists, skipping)"

echo "==> Granting roles/run.invoker to ${SA_EMAIL} on ${SERVICE_NAME} ..."
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --region="${REGION}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker" \
  --project="${PROJECT}"

echo "==> Creating Cloud Tasks queue ${QUEUE_NAME} in ${REGION} ..."
gcloud tasks queues create "${QUEUE_NAME}" \
  --location="${REGION}" \
  --project="${PROJECT}" 2>/dev/null \
  || echo "    (already exists, skipping)"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --format="value(status.url)")

echo ""
echo "Cloud Tasks setup complete."
echo ""
echo "Set these environment variables on the Cloud Run service:"
echo ""
echo "  CLOUD_TASKS_QUEUE=${QUEUE_PATH}"
echo "  CLOUD_RUN_SERVICE_URL=${SERVICE_URL}"
echo "  CLOUD_TASKS_SA=${SA_EMAIL}"
echo ""
echo "After confirming task delivery is reliable, remove --min-instances 1"
echo "from the Cloud Run deployment to allow scale-to-zero."
