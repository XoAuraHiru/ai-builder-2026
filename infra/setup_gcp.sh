#!/usr/bin/env bash
# One-time project setup (idempotent; Cloud SQL creation takes 5-10 minutes).
# Usage: BILLING_ACCOUNT=<id from `gcloud billing accounts list`> bash infra/setup_gcp.sh
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
REGION="${REGION:-us-central1}"
BILLING="${BILLING_ACCOUNT:?set BILLING_ACCOUNT (gcloud billing accounts list)}"
# Scope the project to this process only; the caller's active gcloud configuration is left alone.
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"

step() { printf '\n== %s\n' "$1"; }

step "project"
gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1 || gcloud projects create "$PROJECT_ID" --name="Atrium AI Builder Cup"
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING" >/dev/null

step "APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  sqladmin.googleapis.com secretmanager.googleapis.com pubsub.googleapis.com aiplatform.googleapis.com \
  documentai.googleapis.com discoveryengine.googleapis.com bigquery.googleapis.com \
  firebase.googleapis.com identitytoolkit.googleapis.com iam.googleapis.com

step "Cloud SQL"
if ! gcloud sql instances describe atrium-db >/dev/null 2>&1; then
  gcloud sql instances create atrium-db --database-version=POSTGRES_16 --edition=ENTERPRISE \
    --tier=db-f1-micro --region="$REGION" --storage-size=10GB --availability-type=ZONAL
fi
gcloud sql databases describe atrium --instance=atrium-db >/dev/null 2>&1 || gcloud sql databases create atrium --instance=atrium-db
DB_PASS="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
if gcloud sql users list --instance=atrium-db --format='value(name)' | grep -qx atrium; then
  gcloud sql users set-password atrium --instance=atrium-db --password="$DB_PASS" >/dev/null
else
  gcloud sql users create atrium --instance=atrium-db --password="$DB_PASS" >/dev/null
fi
CONN="$(gcloud sql instances describe atrium-db --format='value(connectionName)')"
DB_URL="postgresql+pg8000://atrium:${DB_PASS}@/atrium?unix_sock=/cloudsql/${CONN}/.s.PGSQL.5432"

step "secret"
gcloud secrets describe atrium-database-url >/dev/null 2>&1 || gcloud secrets create atrium-database-url --replication-policy=automatic
printf '%s' "$DB_URL" | gcloud secrets versions add atrium-database-url --data-file=- >/dev/null

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

step "Firebase"
firebase projects:addfirebase "$PROJECT_ID" >/dev/null 2>&1 && echo "Firebase added" || echo "Firebase not added (run: firebase login, then rerun)"

echo
echo "setup complete for $PROJECT_ID"
echo "manual step for AUTH_MODE=firebase: https://console.firebase.google.com/project/$PROJECT_ID/authentication/providers -> enable Email/Password"
