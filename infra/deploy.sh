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

# --set-env-vars replaces the whole map, so carry the live web origin into CORS on every API redeploy.
PREV_WEB_URL="$(gcloud run services describe atrium-web --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
CORS="http://localhost:3000"
if [ -n "$PREV_WEB_URL" ]; then CORS="${PREV_WEB_URL},${CORS}"; fi

# "^@^" makes @ the separator, because CORS_ORIGINS itself contains a comma.
API_ENV="^@^ENV=dev@AUTH_MODE=${AUTH_MODE}@GCP_PROJECT=${PROJECT_ID}@GCP_LOCATION=${REGION}"
API_ENV="${API_ENV}@MARKET_DATA_PROVIDER=yfinance@MARKET_CACHE_DIR=/tmp/cache@PUBSUB_ENABLED=true@AUTO_SEED=true"
API_ENV="${API_ENV}@CORS_ORIGINS=${CORS}"

gcloud run deploy atrium-api --source services/api --region "$REGION" --allow-unauthenticated --quiet \
  --service-account "$SA" --add-cloudsql-instances "$CONN" \
  --set-secrets "DATABASE_URL=atrium-database-url:latest" \
  --set-env-vars "$API_ENV" \
  --min-instances 1 --max-instances 3 --memory 1Gi --cpu 1 --timeout 300
API_URL="$(gcloud run services describe atrium-api --region "$REGION" --format='value(status.url)')"

gcloud run deploy atrium-web --source apps/web --region "$REGION" --allow-unauthenticated --quiet \
  --set-env-vars "API_URL=${API_URL},AUTH_MODE=${AUTH_MODE},FIREBASE_PROJECT_ID=${PROJECT_ID},FIREBASE_API_KEY=${FIREBASE_API_KEY:-},FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN:-},FIREBASE_APP_ID=${FIREBASE_APP_ID:-}" \
  --min-instances 1 --max-instances 3 --memory 512Mi
WEB_URL="$(gcloud run services describe atrium-web --region "$REGION" --format='value(status.url)')"

if [ "$WEB_URL" != "$PREV_WEB_URL" ]; then
  # First release, or the web URL changed: the API learns the web origin now.
  gcloud run services update atrium-api --region "$REGION" --quiet \
    --update-env-vars "^@^CORS_ORIGINS=${WEB_URL},http://localhost:3000" >/dev/null
fi
echo "API: $API_URL"
echo "WEB: $WEB_URL"
