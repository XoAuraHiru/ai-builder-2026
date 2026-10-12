#!/usr/bin/env bash
# Deploys the API and web services to Cloud Run.
# Usage: bash infra/deploy.sh            (AUTH_MODE=firebase plus FIREBASE_* vars to require Firebase sign-in)
# Both services scale to zero by default: you pay only while requests are served.
# For the judging window keep them warm: API_MIN_INSTANCES=1 WEB_MIN_INSTANCES=1 bash infra/deploy.sh
set -euo pipefail
# Git Bash on Windows rewrites path-like arguments (https://x, /tmp/x) passed to native programs such as gcloud.
# Exempt only our "^@^" env-var lists; gcloud's own launcher on Windows still needs the conversion.
export MSYS2_ARG_CONV_EXCL='^@^'
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
REGION="${REGION:-us-central1}"
AUTH_MODE="${AUTH_MODE:-dev}"
API_MIN_INSTANCES="${API_MIN_INSTANCES:-0}"
WEB_MIN_INSTANCES="${WEB_MIN_INSTANCES:-0}"
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
cd "$(dirname "$0")/.."
bash infra/preflight.sh

CONN="$(gcloud sql instances describe atrium-db --format='value(connectionName)')"
SA="atrium-api@${PROJECT_ID}.iam.gserviceaccount.com"

# Every URL Cloud Run serves the web app on (it has a project-number URL and a legacy hash URL), comma-separated.
web_origins() {
  local urls
  urls="$(gcloud run services describe atrium-web --region "$REGION" \
    --format='value(metadata.annotations["run.googleapis.com/urls"])' 2>/dev/null || true)"
  urls="$(printf '%s' "$urls" | tr -d '[]" ')"
  if [ -z "$urls" ]; then
    urls="$(gcloud run services describe atrium-web --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
  fi
  printf '%s' "$urls"
}

# --set-env-vars replaces the whole map, so carry the live web origins into CORS on every API redeploy.
PREV_WEB_ORIGINS="$(web_origins)"
CORS="http://localhost:3000"
if [ -n "$PREV_WEB_ORIGINS" ]; then CORS="${PREV_WEB_ORIGINS},${CORS}"; fi

# "^@^" makes @ the separator, because CORS_ORIGINS itself contains a comma.
API_ENV="^@^ENV=dev@AUTH_MODE=${AUTH_MODE}@GCP_PROJECT=${PROJECT_ID}@GCP_LOCATION=${REGION}"
API_ENV="${API_ENV}@MARKET_DATA_PROVIDER=yfinance@MARKET_CACHE_DIR=/tmp/cache@PUBSUB_ENABLED=true@AUTO_SEED=true"
API_ENV="${API_ENV}@CORS_ORIGINS=${CORS}"
# Gemini serves from the global endpoint; ADK reads the GOOGLE_* variables, the app reads LLM_PROVIDER and GEMINI_*.
API_ENV="${API_ENV}@LLM_PROVIDER=gemini@GEMINI_LOCATION=global@GOOGLE_GENAI_USE_ENTERPRISE=true"
API_ENV="${API_ENV}@GOOGLE_CLOUD_PROJECT=${PROJECT_ID}@GOOGLE_CLOUD_LOCATION=global@DOCAI_LOCATION=us"

gcloud run deploy atrium-api --source services/api --region "$REGION" --allow-unauthenticated --quiet \
  --service-account "$SA" --add-cloudsql-instances "$CONN" \
  --set-secrets "DATABASE_URL=atrium-database-url:latest,DOCAI_PROOFING_PROCESSOR=atrium-docai-proofing-processor:latest" \
  --set-env-vars "$API_ENV" \
  --min-instances "$API_MIN_INSTANCES" --max-instances 3 --memory 1Gi --cpu 1 --cpu-boost --timeout 300
API_URL="$(gcloud run services describe atrium-api --region "$REGION" --format='value(status.url)')"

gcloud run deploy atrium-web --source apps/web --region "$REGION" --allow-unauthenticated --quiet \
  --set-env-vars "API_URL=${API_URL},AUTH_MODE=${AUTH_MODE},FIREBASE_PROJECT_ID=${PROJECT_ID},FIREBASE_API_KEY=${FIREBASE_API_KEY:-},FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN:-},FIREBASE_APP_ID=${FIREBASE_APP_ID:-}" \
  --min-instances "$WEB_MIN_INSTANCES" --max-instances 3 --memory 512Mi --cpu-boost
WEB_URL="$(gcloud run services describe atrium-web --region "$REGION" --format='value(status.url)')"

WEB_ORIGINS="$(web_origins)"
if [ "$WEB_ORIGINS" != "$PREV_WEB_ORIGINS" ]; then
  # First release, or the web URLs changed: the API learns the web origins now.
  gcloud run services update atrium-api --region "$REGION" --quiet \
    --update-env-vars "^@^CORS_ORIGINS=${WEB_ORIGINS},http://localhost:3000" >/dev/null
fi
echo "API: $API_URL"
echo "WEB: $WEB_URL"
