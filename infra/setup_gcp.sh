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
if ! gcloud sql instances describe atrium-db >/dev/null 2>&1; then
  gcloud sql instances create atrium-db --database-version=POSTGRES_16 --edition=ENTERPRISE \
    --tier=db-f1-micro --region="$REGION" --storage-size=10GB --availability-type=ZONAL
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

step "image repository"
# `gcloud run deploy --source` pushes here. Keep the three newest images, delete anything older than a day.
gcloud artifacts repositories describe cloud-run-source-deploy --location="$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create cloud-run-source-deploy --repository-format=docker --location="$REGION" \
       --description="Cloud Run source deployments"
POLICY="$(mktemp)"
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
