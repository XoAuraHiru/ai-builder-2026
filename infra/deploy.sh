#!/usr/bin/env bash
# Deploys the API and web services to Cloud Run.
# Usage: bash infra/deploy.sh            (AUTH_MODE=firebase plus FIREBASE_* vars to require Firebase sign-in)
# Both services scale to zero by default: you pay only while requests are served.
# For the judging window keep them warm: API_MIN_INSTANCES=1 WEB_MIN_INSTANCES=1 bash infra/deploy.sh
set -euo pipefail
# Git Bash on Windows rewrites path-like arguments (https://x, /tmp/x) passed to native programs such as gcloud.
# Exempt only our "^@^" env-var lists; gcloud's own launcher on Windows still needs the conversion.
export MSYS2_ARG_CONV_EXCL='^@^;--uri='
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
REGION="${REGION:-us-central1}"
AUTH_MODE="${AUTH_MODE:-dev}"
API_MIN_INSTANCES="${API_MIN_INSTANCES:-0}"
WEB_MIN_INSTANCES="${WEB_MIN_INSTANCES:-0}"
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
cd "$(dirname "$0")/.."
bash infra/preflight.sh
# The deploy gate: every free-tier evaluation suite (golden sets, fixed red-team attacks, fair lending) must pass on
# the committed code. It needs no network; a failing suite exits 1, and set -e stops the deploy here.
(cd services/api && uv run python -m app.governance.evals --tier free)

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

# Firebase Hosting serves the web app too (firebase.json rewrites every path to atrium-web), from these origins.
HOSTING_ORIGINS="https://${PROJECT_ID}.web.app,https://${PROJECT_ID}.firebaseapp.com"

# --set-env-vars replaces the whole map, so carry the live web origins into CORS on every API redeploy.
PREV_WEB_ORIGINS="$(web_origins)"
CORS="${HOSTING_ORIGINS},http://localhost:3000"
if [ -n "$PREV_WEB_ORIGINS" ]; then CORS="${PREV_WEB_ORIGINS},${CORS}"; fi

# "^@^" makes @ the separator, because CORS_ORIGINS itself contains a comma.
API_ENV="^@^ENV=dev@AUTH_MODE=${AUTH_MODE}@GCP_PROJECT=${PROJECT_ID}@GCP_LOCATION=${REGION}"
API_ENV="${API_ENV}@MARKET_DATA_PROVIDER=yfinance@MARKET_CACHE_DIR=/tmp/cache@PUBSUB_ENABLED=true@AUTO_SEED=true"
API_ENV="${API_ENV}@CORS_ORIGINS=${CORS}"
# Gemini serves from the global endpoint; ADK reads the GOOGLE_* variables, the app reads LLM_PROVIDER and GEMINI_*.
API_ENV="${API_ENV}@LLM_PROVIDER=gemini@GEMINI_LOCATION=global@GOOGLE_GENAI_USE_ENTERPRISE=true"
API_ENV="${API_ENV}@GOOGLE_CLOUD_PROJECT=${PROJECT_ID}@GOOGLE_CLOUD_LOCATION=global@DOCAI_LOCATION=us"
API_ENV="${API_ENV}@FUND_SEARCH_ENGINE=atrium-fund-search@FUND_SEARCH_LOCATION=global"
# The Models page's "Run the live checks" button starts this job with the API's own identity.
API_ENV="${API_ENV}@EVALS_JOB=projects/${PROJECT_ID}/locations/${REGION}/jobs/atrium-evals"
# Report-only monitoring for the judging window: visitors' exploratory accepts and rejects must not switch a model
# off. MONITORING_TRIPS=true bash infra/deploy.sh restores trips. The live checks still trip breakers either way.
API_ENV="${API_ENV}@MONITORING_TRIPS=${MONITORING_TRIPS:-false}"
# The live inbox: the API, the day-end and the live checks write notices to Firestore.
API_ENV="${API_ENV}@FIRESTORE_ENABLED=true"

# The API signs the inbox's custom tokens as its own account. The address has an @, the separator of the list above,
# so it goes in a second --set-env-vars, which gcloud merges into the first.
gcloud run deploy atrium-api --source services/api --region "$REGION" --allow-unauthenticated --quiet \
  --service-account "$SA" --add-cloudsql-instances "$CONN" \
  --set-secrets "DATABASE_URL=atrium-database-url:latest,DOCAI_PROOFING_PROCESSOR=atrium-docai-proofing-processor:latest,DOCAI_STATEMENT_PROCESSOR=atrium-docai-statement-processor:latest,BLIND_INDEX_KEY=atrium-blind-index-key:latest" \
  --set-env-vars "$API_ENV" --set-env-vars "FIREBASE_SERVICE_ACCOUNT=${SA}" \
  --min-instances "$API_MIN_INSTANCES" --max-instances 3 --memory 1Gi --cpu 1 --cpu-boost --timeout 300
API_URL="$(gcloud run services describe atrium-api --region "$REGION" --format='value(status.url)')"

# The day-end (app/ops/day_end.py) runs as a Cloud Run job from the image just deployed, so there is no second build.
SECRETS="DATABASE_URL=atrium-database-url:latest,DOCAI_STATEMENT_PROCESSOR=atrium-docai-statement-processor:latest,BLIND_INDEX_KEY=atrium-blind-index-key:latest"
IMAGE="$(gcloud run services describe atrium-api --region "$REGION" --format='value(spec.template.spec.containers[0].image)')"
gcloud run jobs deploy atrium-day-end --image "$IMAGE" --region "$REGION" --quiet \
  --service-account "$SA" --set-cloudsql-instances "$CONN" --set-secrets "$SECRETS" --set-env-vars "$API_ENV" \
  --command python --args=-m,app.ops.day_end --max-retries 1 --task-timeout 900 --memory 1Gi --cpu 1 >/dev/null
# Weekdays at 5:15 pm in New York, once every close has printed. Scheduler calls the Cloud Run Admin API as the
# service account, which may start the job (roles/run.invoker).
RUN_URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/atrium-day-end:run"
SCHEDULE=(--location "$REGION" --schedule "15 17 * * 1-5" --time-zone "America/New_York" --uri="$RUN_URI"
          --http-method POST --oauth-service-account-email "$SA" --quiet)
if gcloud scheduler jobs describe atrium-day-end --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http atrium-day-end "${SCHEDULE[@]}" >/dev/null
else
  gcloud scheduler jobs create http atrium-day-end "${SCHEDULE[@]}" >/dev/null
fi
echo "day-end job: atrium-day-end, weekdays 5:15 pm America/New_York"

# The live checks (app/governance/evals) run as a job from the same image: Gemini, the ADK agent and the red team
# against the golden sets, results stored for the Models page. It also gets the ID proofing processor so a run with
# --with-documents can read the specimen cards. GIT_SHA records which commit was checked.
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
EVALS_SECRETS="${SECRETS},DOCAI_PROOFING_PROCESSOR=atrium-docai-proofing-processor:latest"
gcloud run jobs deploy atrium-evals --image "$IMAGE" --region "$REGION" --quiet \
  --service-account "$SA" --set-cloudsql-instances "$CONN" --set-secrets "$EVALS_SECRETS" \
  --set-env-vars "${API_ENV}@GIT_SHA=${GIT_SHA}" \
  --command python --args=-m,app.governance.evals,--tier,live,--store,--trigger,deploy \
  --max-retries 0 --task-timeout 2700 --memory 1Gi --cpu 1 >/dev/null
# The API runs as $SA; the button starts the job through the Cloud Run Admin API, which needs roles/run.invoker.
gcloud run jobs add-iam-policy-binding atrium-evals --region "$REGION" \
  --member "serviceAccount:${SA}" --role roles/run.invoker --quiet >/dev/null
echo "evals job: atrium-evals (live checks after each deploy and from the Models page)"

gcloud run deploy atrium-web --source apps/web --region "$REGION" --allow-unauthenticated --quiet \
  --set-env-vars "API_URL=${API_URL},AUTH_MODE=${AUTH_MODE},FIREBASE_PROJECT_ID=${PROJECT_ID},FIREBASE_API_KEY=${FIREBASE_API_KEY:-},FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN:-},FIREBASE_APP_ID=${FIREBASE_APP_ID:-}" \
  --min-instances "$WEB_MIN_INSTANCES" --max-instances 3 --memory 512Mi --cpu-boost
WEB_URL="$(gcloud run services describe atrium-web --region "$REGION" --format='value(status.url)')"

WEB_ORIGINS="$(web_origins)"
if [ "$WEB_ORIGINS" != "$PREV_WEB_ORIGINS" ]; then
  # First release, or the web URLs changed: the API learns the web origins now.
  gcloud run services update atrium-api --region "$REGION" --quiet \
    --update-env-vars "^@^CORS_ORIGINS=${WEB_ORIGINS},${HOSTING_ORIGINS},http://localhost:3000" >/dev/null
fi
echo "API: $API_URL"
echo "WEB: $WEB_URL"

# Start the live checks against what was just deployed, without waiting: about ten minutes and $0.15 of Gemini.
gcloud run jobs execute atrium-evals --region "$REGION" --async --quiet >/dev/null
echo "Live checks started (atrium-evals); results appear on /compliance/models in about ten minutes."

# The inbox's Firestore security rules, and Firebase Hosting in front of the web service. Last, and never fatal: the
# services above are already live, and the step can be rerun by hand.
if command -v firebase >/dev/null 2>&1; then
  if firebase deploy --only firestore:rules,hosting --project "$PROJECT_ID" --non-interactive; then
    echo "Firebase: Firestore rules and Hosting deployed (https://${PROJECT_ID}.web.app)"
  else
    echo "Firebase deploy failed: run firebase login, then: firebase deploy --only firestore:rules,hosting --project ${PROJECT_ID}"
  fi
else
  echo "Firebase CLI not found: skipped the Firestore rules and Hosting (npm install -g firebase-tools, then rerun)"
fi
