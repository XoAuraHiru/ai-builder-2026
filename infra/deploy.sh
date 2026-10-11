#!/usr/bin/env bash
# Deploys the API and web services to Cloud Run.
# Usage: bash infra/deploy.sh            (AUTH_MODE=firebase plus FIREBASE_* vars to require Firebase sign-in)
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
REGION="${REGION:-us-central1}"
AUTH_MODE="${AUTH_MODE:-dev}"
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
cd "$(dirname "$0")/.."
bash infra/preflight.sh

CONN="$(gcloud sql instances describe atrium-db --format='value(connectionName)')"
SA="atrium-api@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud run deploy atrium-api --source services/api --region "$REGION" --allow-unauthenticated --quiet \
  --service-account "$SA" --add-cloudsql-instances "$CONN" \
  --set-secrets "DATABASE_URL=atrium-database-url:latest" \
  --set-env-vars "ENV=dev,AUTH_MODE=${AUTH_MODE},GCP_PROJECT=${PROJECT_ID},GCP_LOCATION=${REGION},MARKET_DATA_PROVIDER=yfinance,MARKET_CACHE_DIR=/tmp/cache,PUBSUB_ENABLED=true,AUTO_SEED=true" \
  --min-instances 1 --max-instances 3 --memory 1Gi --cpu 1 --timeout 300
API_URL="$(gcloud run services describe atrium-api --region "$REGION" --format='value(status.url)')"

gcloud run deploy atrium-web --source apps/web --region "$REGION" --allow-unauthenticated --quiet \
  --set-env-vars "API_URL=${API_URL},AUTH_MODE=${AUTH_MODE},FIREBASE_PROJECT_ID=${PROJECT_ID},FIREBASE_API_KEY=${FIREBASE_API_KEY:-},FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN:-},FIREBASE_APP_ID=${FIREBASE_APP_ID:-}" \
  --min-instances 1 --max-instances 3 --memory 512Mi
WEB_URL="$(gcloud run services describe atrium-web --region "$REGION" --format='value(status.url)')"

gcloud run services update atrium-api --region "$REGION" --quiet \
  --update-env-vars "^@^CORS_ORIGINS=${WEB_URL},http://localhost:3000" >/dev/null
echo "API: $API_URL"
echo "WEB: $WEB_URL"
