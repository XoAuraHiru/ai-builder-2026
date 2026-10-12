#!/usr/bin/env bash
# One-time project setup. Idempotent: safe to rerun, and a rerun never rotates the live database password.
# Cloud SQL creation takes 5-10 minutes the first time.
# Usage: BILLING_ACCOUNT=<id from `gcloud billing accounts list`> [BUDGET_USD=15] bash infra/setup_gcp.sh
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
REGION="${REGION:-us-central1}"
BILLING="${BILLING_ACCOUNT:?set BILLING_ACCOUNT (gcloud billing accounts list)}"
BUDGET_USD="${BUDGET_USD:-15}"
# Scope the project to this process only; the caller's active gcloud configuration is left alone.
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
cd "$(dirname "$0")/.."  # paths below are relative to the repository root

step() { printf '\n== %s\n' "$1"; }
# Counts exact-line matches. grep -c reads all input, so it never SIGPIPEs the producer under pipefail.
count_lines() { grep -cx -- "$1" || true; }

step "project"
gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1 || gcloud projects create "$PROJECT_ID" --name="Atrium AI Builder Cup"
# Link only when needed: re-linking an already-linked project fails once the account is at its project quota.
LINKED="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingAccountName)' 2>/dev/null || true)"
if [ "$LINKED" != "billingAccounts/${BILLING}" ]; then
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING" >/dev/null
fi

step "APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com pubsub.googleapis.com aiplatform.googleapis.com \
  documentai.googleapis.com discoveryengine.googleapis.com bigquery.googleapis.com \
  firebase.googleapis.com identitytoolkit.googleapis.com iam.googleapis.com billingbudgets.googleapis.com

step "Cloud SQL"
# Smallest tier (shared core), zonal, 10 GB SSD, daily automated backups (a few MB of data: about a cent a month).
if ! gcloud sql instances describe atrium-db >/dev/null 2>&1; then
  gcloud sql instances create atrium-db --database-version=POSTGRES_16 --edition=ENTERPRISE \
    --tier=db-f1-micro --region="$REGION" --storage-size=10GB --availability-type=ZONAL \
    --backup-start-time=03:00 --retained-backups-count=7
elif [ "$(gcloud sql instances describe atrium-db --format='value(settings.backupConfiguration.enabled)')" != "True" ]; then
  gcloud sql instances patch atrium-db --backup-start-time=03:00 --retained-backups-count=7 --quiet >/dev/null
fi
gcloud sql databases describe atrium --instance=atrium-db >/dev/null 2>&1 || gcloud sql databases create atrium --instance=atrium-db

step "database credentials"
gcloud secrets describe atrium-database-url >/dev/null 2>&1 || gcloud secrets create atrium-database-url --replication-policy=automatic
HAS_USER="$(gcloud sql users list --instance=atrium-db --format='value(name)' | count_lines atrium)"
HAS_SECRET="$(gcloud secrets versions list atrium-database-url --filter='state=ENABLED' --limit=1 --format='value(name)' 2>/dev/null || true)"
if [ "$HAS_USER" -gt 0 ] && [ -n "$HAS_SECRET" ]; then
  echo "database user and secret already exist; password unchanged"
else
  # openssl, not `tr </dev/urandom | head`: under pipefail that pipeline exits 141 (SIGPIPE) and kills the script.
  DB_PASS="$(openssl rand -hex 16)"
  if [ "$HAS_USER" -gt 0 ]; then
    gcloud sql users set-password atrium --instance=atrium-db --password="$DB_PASS" >/dev/null
  else
    gcloud sql users create atrium --instance=atrium-db --password="$DB_PASS" >/dev/null
  fi
  CONN="$(gcloud sql instances describe atrium-db --format='value(connectionName)')"
  DB_URL="postgresql+pg8000://atrium:${DB_PASS}@/atrium?unix_sock=/cloudsql/${CONN}/.s.PGSQL.5432"
  printf '%s' "$DB_URL" | gcloud secrets versions add atrium-database-url --data-file=- >/dev/null
  echo "database credentials stored in Secret Manager"
fi

step "service account"
SA="atrium-api@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || gcloud iam service-accounts create atrium-api --display-name="Atrium API"
for ROLE in roles/cloudsql.client roles/secretmanager.secretAccessor roles/pubsub.publisher roles/aiplatform.user \
            roles/documentai.apiUser roles/discoveryengine.viewer roles/bigquery.dataEditor roles/bigquery.jobUser \
            roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" --role="$ROLE" \
    --condition=None --quiet >/dev/null
done

step "Pub/Sub"
gcloud pubsub topics describe atrium-events >/dev/null 2>&1 || gcloud pubsub topics create atrium-events

step "BigQuery event log"
# Every domain event (AI decisions included, metadata only) lands in BigQuery through a Pub/Sub subscription: no code.
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
bq --project_id="$PROJECT_ID" show --dataset "$PROJECT_ID:atrium" >/dev/null 2>&1 \
  || bq --project_id="$PROJECT_ID" --location=US mk --dataset --description="Atrium events, AI decision log, models" \
       "$PROJECT_ID:atrium" >/dev/null
bq --project_id="$PROJECT_ID" query --use_legacy_sql=false --quiet \
  "CREATE TABLE IF NOT EXISTS \`$PROJECT_ID.atrium.events\` (subscription_name STRING, message_id STRING, publish_time TIMESTAMP, data JSON, attributes JSON) PARTITION BY DATE(publish_time)" >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role=roles/bigquery.dataEditor --condition=None --quiet >/dev/null
gcloud pubsub subscriptions describe atrium-events-bq >/dev/null 2>&1 \
  || gcloud pubsub subscriptions create atrium-events-bq --topic=atrium-events \
       --bigquery-table="$PROJECT_ID:atrium.events" --write-metadata >/dev/null

step "Document AI identity proofing"
# There is no gcloud command group for Document AI processors, so this uses the REST API.
DOCAI="https://us-documentai.googleapis.com/v1/projects/${PROJECT_ID}/locations/us/processors"
TOKEN="$(gcloud auth print-access-token)"
PY="$(command -v python3 || command -v python)"
PROCESSOR_ID="$(curl -s -H "Authorization: Bearer ${TOKEN}" "$DOCAI" | "$PY" -c 'import json, sys
d = json.load(sys.stdin)
print(next((p["name"].rsplit("/", 1)[-1] for p in d.get("processors", []) if p.get("displayName") == "atrium-id-proofing"), ""))')"
if [ -z "$PROCESSOR_ID" ]; then
  PROCESSOR_ID="$(curl -s -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
    -d '{"type": "ID_PROOFING_PROCESSOR", "displayName": "atrium-id-proofing"}' "$DOCAI" \
    | "$PY" -c 'import json, sys; print(json.load(sys.stdin)["name"].rsplit("/", 1)[-1])')"
fi
gcloud secrets describe atrium-docai-proofing-processor >/dev/null 2>&1 \
  || gcloud secrets create atrium-docai-proofing-processor --replication-policy=automatic >/dev/null
STORED="$(gcloud secrets versions access latest --secret=atrium-docai-proofing-processor 2>/dev/null || true)"
if [ "$STORED" != "$PROCESSOR_ID" ]; then
  printf '%s' "$PROCESSOR_ID" | gcloud secrets versions add atrium-docai-proofing-processor --data-file=- >/dev/null
fi
echo "ID proofing processor: $PROCESSOR_ID"

step "Vertex AI Search fund documents"
# The fund fact sheets (HTML built by `python -m app.knowledge.build`) are indexed with layout-aware chunking; the API
# searches them to ground every fund answer, and falls back to its local index if search is unreachable.
BUCKET="gs://${PROJECT_ID}-fund-docs"
gcloud storage buckets describe "$BUCKET" >/dev/null 2>&1 \
  || gcloud storage buckets create "$BUCKET" --location=US --uniform-bucket-level-access >/dev/null
gcloud storage cp services/api/app/knowledge/html/*.html "$BUCKET/funds/" >/dev/null
DE="https://discoveryengine.googleapis.com/v1/projects/${PROJECT_ID}/locations/global/collections/default_collection"
DE_HEADERS=(-H "Authorization: Bearer ${TOKEN}" -H "X-Goog-User-Project: ${PROJECT_ID}" -H "Content-Type: application/json")
if ! curl -sf "${DE_HEADERS[@]}" "$DE/dataStores/atrium-fund-docs" >/dev/null; then
  curl -sf -X POST "${DE_HEADERS[@]}" "$DE/dataStores?dataStoreId=atrium-fund-docs" -d '{
    "displayName": "Atrium fund documents", "industryVertical": "GENERIC", "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
    "contentConfig": "CONTENT_REQUIRED",
    "documentProcessingConfig": {"defaultParsingConfig": {"layoutParsingConfig": {}},
      "chunkingConfig": {"layoutBasedChunkingConfig": {"chunkSize": 300, "includeAncestorHeadings": true}}}}' >/dev/null
  for _ in $(seq 1 30); do curl -sf "${DE_HEADERS[@]}" "$DE/dataStores/atrium-fund-docs" >/dev/null && break; sleep 5; done
fi
# FULL reconciliation keeps the index identical to the bucket: rerun this step after rebuilding the documents.
curl -sf -X POST "${DE_HEADERS[@]}" "$DE/dataStores/atrium-fund-docs/branches/default_branch/documents:import" \
  -d "{\"gcsSource\": {\"inputUris\": [\"${BUCKET}/funds/*.html\"], \"dataSchema\": \"content\"}, \"reconciliationMode\": \"FULL\"}" >/dev/null
if ! curl -sf "${DE_HEADERS[@]}" "$DE/engines/atrium-fund-search" >/dev/null; then
  curl -sf -X POST "${DE_HEADERS[@]}" "$DE/engines?engineId=atrium-fund-search" -d '{
    "displayName": "Atrium fund search", "solutionType": "SOLUTION_TYPE_SEARCH", "industryVertical": "GENERIC",
    "dataStoreIds": ["atrium-fund-docs"], "searchEngineConfig": {"searchTier": "SEARCH_TIER_ENTERPRISE"}}' >/dev/null
fi
echo "fund search app: atrium-fund-search (the import runs in the background for a few minutes)"

step "image repository"
# `gcloud run deploy --source` pushes here. Keep the three newest images, delete anything older than a day.
gcloud artifacts repositories describe cloud-run-source-deploy --location="$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create cloud-run-source-deploy --repository-format=docker --location="$REGION" \
       --description="Cloud Run source deployments"
# Relative path: means the same thing to gcloud on Linux and on Windows (Git Bash).
POLICY=".atrium-cleanup-policy.json"
trap 'rm -f "$POLICY"' EXIT
cat > "$POLICY" <<'JSON'
[
  {"name": "keep-newest-3", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 3}},
  {"name": "delete-older-than-1d", "action": {"type": "Delete"}, "condition": {"tagState": "any", "olderThan": "1d"}}
]
JSON
gcloud artifacts repositories set-cleanup-policies cloud-run-source-deploy --location="$REGION" \
  --policy="$POLICY" --no-dry-run --quiet >/dev/null
rm -f "$POLICY"

step "budget alert"
BUDGETS="$(gcloud billing budgets list --billing-account="$BILLING" --format='value(displayName)' 2>/dev/null || true)"
if [ "$(printf '%s\n' "$BUDGETS" | count_lines "Atrium monthly budget")" -gt 0 ]; then
  echo "budget already exists"
else
  # Emails the billing account's admins at 50%, 90% and 100% of actual spend, and when the forecast passes 100%.
  gcloud billing budgets create --billing-account="$BILLING" --display-name="Atrium monthly budget" \
    --budget-amount="${BUDGET_USD}USD" --filter-projects="projects/${PROJECT_ID}" \
    --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0 \
    --threshold-rule=percent=1.0,basis=forecasted-spend >/dev/null
  echo "budget alert created at ${BUDGET_USD} USD per month"
fi

step "Firebase"
firebase projects:addfirebase "$PROJECT_ID" >/dev/null 2>&1 && echo "Firebase added" || echo "Firebase not added (already added, or run: firebase login)"

echo
echo "setup complete for $PROJECT_ID"
echo "manual step for AUTH_MODE=firebase: https://console.firebase.google.com/project/$PROJECT_ID/authentication/providers -> enable Email/Password"
