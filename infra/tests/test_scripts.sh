#!/usr/bin/env bash
# Runs setup_gcp.sh and deploy.sh against fake gcloud/firebase binaries and checks what they would do.
# Usage: bash infra/tests/test_scripts.sh      (no cloud access needed; exit 0 = all pass)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/bin"
export FAKE_LOG="$WORK/calls.log"
FAKE_PY="$(command -v python || command -v python3)"
export FAKE_PY

# FAKE_EXISTING=1 simulates a project where setup already ran once; FAKE_WEB_EXISTS=1 a live web service.
cat > "$WORK/bin/gcloud" <<'FAKE'
#!/usr/bin/env bash
# Record the arguments through a native program, as the real gcloud receives them: on Windows, Git Bash
# rewrites path-like arguments (for example https:// becomes https;\) when it calls a non-MSYS executable.
"$FAKE_PY" -c 'import sys; print("gcloud " + " ".join(sys.argv[1:]))' "$@" >> "$FAKE_LOG"
case "$*" in *"--data-file=-"*) cat >/dev/null ;; esac
case "$*" in "run deploy atrium-web"*) touch "$FAKE_LOG.web" ;; esac
case "$*" in
  "auth list"*) echo "tester@example.test" ;;
  *"sql instances describe"*"connectionName"*) echo "proj:us-central1:atrium-db" ;;
  *"sql instances describe"*"backupConfiguration"*) [ -n "${FAKE_EXISTING:-}" ] && echo "False" ;;
  *"sql users list"*) [ -n "${FAKE_EXISTING:-}" ] && echo "atrium" || echo "postgres" ;;
  *"secrets versions list"*) [ -n "${FAKE_EXISTING:-}" ] && echo "projects/p/secrets/atrium-database-url/versions/1" ;;
  *"billing budgets list"*) [ -n "${FAKE_EXISTING:-}" ] && echo "Atrium monthly budget" ;;
  *"billing projects describe"*) [ -n "${FAKE_EXISTING:-}" ] && echo "billingAccounts/TEST-BILLING" ;;
  *"run services describe atrium-web"*"run.googleapis.com/urls"*)
    { [ -n "${FAKE_WEB_EXISTS:-}" ] || [ -f "$FAKE_LOG.web" ]; } \
      && echo '["https://atrium-web-123.us-central1.run.app","https://atrium-web-test.a.run.app"]' || exit 1 ;;
  *"run services describe atrium-web"*) { [ -n "${FAKE_WEB_EXISTS:-}" ] || [ -f "$FAKE_LOG.web" ]; } && echo "https://atrium-web-test.a.run.app" || exit 1 ;;
  *"run services describe atrium-api"*) echo "https://atrium-api-test.a.run.app" ;;
  *"secrets versions access"*) [ -n "${FAKE_EXISTING:-}" ] && printf 'abc123' ;;
  "projects describe"*"projectNumber"*) echo "1234" ;;
  "projects describe"*) exit 0 ;;
  *" describe "*) [ -n "${FAKE_EXISTING:-}" ] && exit 0 || exit 1 ;;
esac
exit 0
FAKE
cat > "$WORK/bin/bq" <<'FAKE'
#!/usr/bin/env bash
echo "bq $*" >> "$FAKE_LOG"
case "$*" in *" show "*) [ -n "${FAKE_EXISTING:-}" ] && exit 0 || exit 1 ;; esac
exit 0
FAKE
cat > "$WORK/bin/curl" <<'FAKE'
#!/usr/bin/env bash
echo "curl $*" >> "$FAKE_LOG"
case "$*" in
  *discoveryengine*"documents:import"*) echo '{"name": "operations/import-1"}' ;;
  *discoveryengine*"dataStores?dataStoreId"*) touch "$FAKE_LOG.datastore"; echo '{"name": "operations/create-datastore"}' ;;
  *discoveryengine*"engines?engineId"*) echo '{"name": "operations/create-engine"}' ;;
  *discoveryengine*"dataStores/atrium-fund-docs"*)
    { [ -n "${FAKE_EXISTING:-}" ] || [ -f "$FAKE_LOG.datastore" ]; } && echo '{"name": "atrium-fund-docs"}' || exit 22 ;;
  *discoveryengine*"engines/atrium-fund-search"*) [ -n "${FAKE_EXISTING:-}" ] && echo '{"name": "atrium-fund-search"}' || exit 22 ;;
  *"-X POST"*) echo '{"name": "projects/1/locations/us/processors/new456", "type": "ID_PROOFING_PROCESSOR"}' ;;
  *) if [ -n "${FAKE_EXISTING:-}" ]; then
       echo '{"processors": [{"name": "projects/1/locations/us/processors/abc123", "displayName": "atrium-id-proofing"}, {"name": "projects/1/locations/us/processors/abc123", "displayName": "atrium-bank-statements"}]}'
     else echo '{}'; fi ;;
esac
FAKE
printf '#!/usr/bin/env bash\necho "firebase $*" >> "$FAKE_LOG"\nexit 1\n' > "$WORK/bin/firebase"
# The deploy gate runs the free evaluation suites through uv; FAKE_GATE_FAILS=1 makes it fail.
cat > "$WORK/bin/uv" <<'FAKE'
#!/usr/bin/env bash
echo "uv $*" >> "$FAKE_LOG"
[ -n "${FAKE_GATE_FAILS:-}" ] && exit 1
exit 0
FAKE
chmod +x "$WORK/bin/gcloud" "$WORK/bin/firebase" "$WORK/bin/bq" "$WORK/bin/curl" "$WORK/bin/uv"
export PATH="$WORK/bin:$PATH"

FAILS=0
check() { if eval "$2"; then printf '  pass %s\n' "$1"; else printf '  FAIL %s\n' "$1"; FAILS=$((FAILS + 1)); fi; }
cd "$ROOT"

echo "setup_gcp.sh on an empty project"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.datastore"
BILLING_ACCOUNT=TEST-BILLING bash infra/setup_gcp.sh > "$WORK/setup.out" 2>&1
STATUS=$?
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "stores the database URL secret" 'grep -q "secrets versions add atrium-database-url" "$FAKE_LOG"'
check "creates the service account" 'grep -q "iam service-accounts create atrium-api" "$FAKE_LOG"'
check "creates the Pub/Sub topic" 'grep -q "pubsub topics create atrium-events" "$FAKE_LOG"'
check "creates the database with daily backups" 'grep "sql instances create atrium-db" "$FAKE_LOG" | grep -q -- "--backup-start-time"'
check "creates the image repository" 'grep -q "artifacts repositories create cloud-run-source-deploy" "$FAKE_LOG"'
check "sets an image cleanup policy" 'grep -q "artifacts repositories set-cleanup-policies cloud-run-source-deploy" "$FAKE_LOG"'
check "creates a project-scoped budget alert" 'grep "billing budgets create" "$FAKE_LOG" | grep -q "filter-projects=projects/atrium-cup-2026"'
check "creates the BigQuery dataset" 'grep -q "^bq .*mk --dataset" "$FAKE_LOG"'
check "creates the events table" 'grep "^bq .*query" "$FAKE_LOG" | grep -q "CREATE TABLE IF NOT EXISTS"'
check "lets Pub/Sub write to BigQuery" 'grep -q "service-1234@gcp-sa-pubsub.iam.gserviceaccount.com" "$FAKE_LOG"'
check "creates the BigQuery subscription" 'grep "pubsub subscriptions create atrium-events-bq" "$FAKE_LOG" | grep -q "bigquery-table=atrium-cup-2026:atrium.events"'
check "creates the ID proofing processor" 'grep "^curl" "$FAKE_LOG" | grep -q "ID_PROOFING_PROCESSOR"'
check "stores the processor id as a secret" 'grep -q "secrets versions add atrium-docai-proofing-processor" "$FAKE_LOG"'
check "creates the fund-documents bucket" 'grep -q "storage buckets create gs://atrium-cup-2026-fund-docs" "$FAKE_LOG"'
check "uploads the fund fact sheets" 'grep "storage cp" "$FAKE_LOG" | grep -q "ATR-BAL.html.*gs://atrium-cup-2026-fund-docs/funds/"'
check "creates the search data store with layout chunking" 'grep -q "dataStoreId=atrium-fund-docs" "$FAKE_LOG" && grep -q "layoutBasedChunkingConfig" "$FAKE_LOG"'
check "imports the documents with full reconciliation" 'grep -q "documents:import" "$FAKE_LOG" && grep -q "\"FULL\"" "$FAKE_LOG"'
check "creates an Enterprise search app" 'grep -q "engineId=atrium-fund-search" "$FAKE_LOG" && grep -q "SEARCH_TIER_ENTERPRISE" "$FAKE_LOG"'
check "enables Cloud Scheduler" 'grep "services enable" "$FAKE_LOG" | grep -q "cloudscheduler.googleapis.com"'
check "lets the service account start the day-end job" 'grep -q "add-iam-policy-binding.*roles/run.invoker" "$FAKE_LOG"'
check "creates the bank statement processor" 'grep "^curl" "$FAKE_LOG" | grep -q "BANK_STATEMENT_PROCESSOR"'
check "stores the statement processor id as a secret" 'grep -q "secrets versions add atrium-docai-statement-processor" "$FAKE_LOG"'
check "creates the blind-index key once" 'grep -q "secrets versions add atrium-blind-index-key" "$FAKE_LOG"'

echo "setup_gcp.sh rerun on a project that is already set up"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.datastore"
FAKE_EXISTING=1 BILLING_ACCOUNT=TEST-BILLING bash infra/setup_gcp.sh > "$WORK/setup2.out" 2>&1
STATUS=$?
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "does not re-link billing (fails at the billing project quota)" '! grep -q "billing projects link" "$FAKE_LOG"'
check "turns on backups for an existing database without them" 'grep -q "sql instances patch atrium-db.*--backup-start-time" "$FAKE_LOG"'
check "leaves the live database password alone" '! grep -q "sql users set-password" "$FAKE_LOG"'
check "does not add a new secret version" '! grep -q "secrets versions add" "$FAKE_LOG"'
check "does not create a second budget" '! grep -q "billing budgets create" "$FAKE_LOG"'
check "does not recreate the dataset or subscription" '! grep -q "mk --dataset" "$FAKE_LOG" && ! grep -q "subscriptions create" "$FAKE_LOG"'
check "reuses the existing ID proofing processor" '! grep -q "ID_PROOFING_PROCESSOR" "$FAKE_LOG"'
check "reuses the existing bank statement processor" '! grep -q "BANK_STATEMENT_PROCESSOR" "$FAKE_LOG"'
check "reuses the data store and search app" '! grep -q "dataStoreId=" "$FAKE_LOG" && ! grep -q "engineId=" "$FAKE_LOG"'
check "still re-imports the documents" 'grep -q "documents:import" "$FAKE_LOG"'

echo "deploy.sh when the web service already exists"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web" "$FAKE_LOG.datastore"
FAKE_WEB_EXISTS=1 bash infra/deploy.sh > "$WORK/deploy.out" 2>&1
STATUS=$?
API_DEPLOY="$(grep -m1 "run deploy atrium-api" "$FAKE_LOG")"
WEB_DEPLOY="$(grep -m1 "run deploy atrium-web" "$FAKE_LOG")"
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "API deploy keeps CORS for the live web origin" 'echo "$API_DEPLOY" | grep -q "CORS_ORIGINS=.*https://atrium-web-test.a.run.app"'
check "API deploy allows both Cloud Run URLs of the web service" 'echo "$API_DEPLOY" | grep -q "https://atrium-web-123.us-central1.run.app"'
check "API env values reach gcloud unmangled" 'echo "$API_DEPLOY" | grep -q "MARKET_CACHE_DIR=/tmp/cache@" && echo "$API_DEPLOY" | grep -q "CORS_ORIGINS=https://atrium-web-123.us-central1.run.app,"'
check "API runs Gemini from the global endpoint" 'echo "$API_DEPLOY" | grep -q "LLM_PROVIDER=gemini" && echo "$API_DEPLOY" | grep -q "GOOGLE_CLOUD_LOCATION=global" && echo "$API_DEPLOY" | grep -q "GOOGLE_GENAI_USE_ENTERPRISE=true"'
check "API gets the ID proofing processor from Secret Manager" 'echo "$API_DEPLOY" | grep -q "DOCAI_PROOFING_PROCESSOR=atrium-docai-proofing-processor:latest"'
check "API searches fund documents with Vertex AI Search" 'echo "$API_DEPLOY" | grep -q "FUND_SEARCH_ENGINE=atrium-fund-search@FUND_SEARCH_LOCATION=global"'
check "API gets the statement processor and the blind-index key from Secret Manager" 'echo "$API_DEPLOY" | grep -q "DOCAI_STATEMENT_PROCESSOR=atrium-docai-statement-processor:latest" && echo "$API_DEPLOY" | grep -q "BLIND_INDEX_KEY=atrium-blind-index-key:latest"'
check "deploys the day-end job from the API image" 'grep "run jobs deploy atrium-day-end" "$FAKE_LOG" | grep -q -- "--image" && grep "run jobs deploy atrium-day-end" "$FAKE_LOG" | grep -q "app.ops.day_end"'
check "the day-end job reaches the database and its secrets" 'grep "run jobs deploy atrium-day-end" "$FAKE_LOG" | grep -q -- "--set-cloudsql-instances" && grep "run jobs deploy atrium-day-end" "$FAKE_LOG" | grep -q "BLIND_INDEX_KEY=atrium-blind-index-key:latest"'
check "schedules the day-end on weekday evenings in New York" 'grep "scheduler jobs create http atrium-day-end" "$FAKE_LOG" | grep -q "15 17 \* \* 1-5" && grep "scheduler jobs create http atrium-day-end" "$FAKE_LOG" | grep -q "America/New_York"'
check "Scheduler calls the Cloud Run job API unmangled" 'grep "scheduler jobs create http atrium-day-end" "$FAKE_LOG" | grep -q -- "--uri=https://run.googleapis.com/v2/projects/atrium-cup-2026/locations/us-central1/jobs/atrium-day-end:run"'
check "API keeps one warm instance by default" 'echo "$API_DEPLOY" | grep -q -- "--min-instances 1"'
check "web keeps one warm instance by default" 'echo "$WEB_DEPLOY" | grep -q -- "--min-instances 1"'
check "both services use startup CPU boost" 'echo "$API_DEPLOY" | grep -q -- "--cpu-boost" && echo "$WEB_DEPLOY" | grep -q -- "--cpu-boost"'

check "API source upload leaves out the local virtualenv and tests" 'grep -qx ".venv/" services/api/.gcloudignore && grep -qx "tests/" services/api/.gcloudignore'
line_of() { grep -n -m1 -- "$1" "$FAKE_LOG" | cut -d: -f1; }
check "runs the free evaluation gate before deploying anything" '[ -n "$(line_of "app.governance.evals --tier free")" ] && [ "$(line_of "app.governance.evals --tier free")" -lt "$(line_of "run deploy atrium-api")" ]'
check "API knows the evals job" 'echo "$API_DEPLOY" | grep -q "EVALS_JOB=projects/atrium-cup-2026/locations/us-central1/jobs/atrium-evals"'
check "deploys the evals job from the API image" 'grep "run jobs deploy atrium-evals" "$FAKE_LOG" | grep -q -- "--image" && grep "run jobs deploy atrium-evals" "$FAKE_LOG" | grep -q "app.governance.evals,--tier,live,--store,--trigger,deploy"'
check "the evals job never retries and stops after 75 minutes" 'grep "run jobs deploy atrium-evals" "$FAKE_LOG" | grep -q -- "--max-retries 0" && grep "run jobs deploy atrium-evals" "$FAKE_LOG" | grep -q -- "--task-timeout 4500"'
check "monitoring is report-only unless asked" 'grep "run deploy atrium-api" "$FAKE_LOG" | grep -q "MONITORING_TRIPS=false"'
check "the evals job records the commit it checked" 'grep "run jobs deploy atrium-evals" "$FAKE_LOG" | grep -q "GIT_SHA="'
check "lets the API start the evals job" 'grep "run jobs add-iam-policy-binding atrium-evals" "$FAKE_LOG" | grep -q "serviceAccount:atrium-api@atrium-cup-2026.iam.gserviceaccount.com" && grep "run jobs add-iam-policy-binding atrium-evals" "$FAKE_LOG" | grep -q "roles/run.invoker"'
check "starts the live checks after the web deploys, without waiting" '[ "$(line_of "run jobs execute atrium-evals")" -gt "$(line_of "run deploy atrium-web")" ] && grep "run jobs execute atrium-evals" "$FAKE_LOG" | grep -q -- "--async"'
check "the API, the day-end and the live checks write to the live inbox" 'echo "$API_DEPLOY" | grep -q "@FIRESTORE_ENABLED=true" && grep "run jobs deploy atrium-day-end" "$FAKE_LOG" | grep -q "FIRESTORE_ENABLED=true" && grep "run jobs deploy atrium-evals" "$FAKE_LOG" | grep -q "FIRESTORE_ENABLED=true"'
check "the API signs inbox tokens as its own account, outside the @-separated list" 'echo "$API_DEPLOY" | grep -q -- "--set-env-vars FIREBASE_SERVICE_ACCOUNT=atrium-api@atrium-cup-2026.iam.gserviceaccount.com"'
check "API allows the Firebase Hosting origins" 'echo "$API_DEPLOY" | grep -q "https://atrium-cup-2026.web.app,https://atrium-cup-2026.firebaseapp.com,http://localhost:3000"'
check "deploys the Firestore rules and Hosting last" '[ "$(line_of "firebase deploy --only firestore:rules,hosting --project atrium-cup-2026 --non-interactive")" -gt "$(line_of "run jobs execute atrium-evals")" ]'
check "a failed Firebase step says what to run and does not fail the release" 'grep -q "Firebase deploy failed: run firebase login" "$WORK/deploy.out"'

echo "deploy.sh when a free evaluation suite fails"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web" "$FAKE_LOG.datastore"
FAKE_GATE_FAILS=1 FAKE_WEB_EXISTS=1 bash infra/deploy.sh > "$WORK/deploy-gate.out" 2>&1
STATUS=$?
check "stops with an error (was $STATUS)" '[ "$STATUS" -ne 0 ]'
check "deploys nothing" '! grep -q "run deploy" "$FAKE_LOG"'

echo "deploy.sh with warm instances for the judging window"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web" "$FAKE_LOG.datastore"
FAKE_WEB_EXISTS=1 API_MIN_INSTANCES=1 WEB_MIN_INSTANCES=1 bash infra/deploy.sh > "$WORK/deploy-warm.out" 2>&1
check "API keeps one warm instance" 'grep -m1 "run deploy atrium-api" "$FAKE_LOG" | grep -q -- "--min-instances 1"'
check "web keeps one warm instance" 'grep -m1 "run deploy atrium-web" "$FAKE_LOG" | grep -q -- "--min-instances 1"'
check "an existing schedule is updated, not created twice" 'FAKE_EXISTING=1 FAKE_WEB_EXISTS=1 bash infra/deploy.sh >/dev/null 2>&1; grep -q "scheduler jobs update http atrium-day-end" "$FAKE_LOG"'

echo "deploy.sh on the very first release"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web" "$FAKE_LOG.datastore"
bash infra/deploy.sh > "$WORK/deploy1.out" 2>&1
STATUS=$?
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "sets CORS after the web service exists" 'grep "run services update atrium-api" "$FAKE_LOG" | grep -q "CORS_ORIGINS="'
check "first-release CORS allows both Cloud Run URLs" 'grep "run services update atrium-api" "$FAKE_LOG" | grep -q "https://atrium-web-123.us-central1.run.app"'
check "first-release CORS allows the Firebase Hosting origins" 'grep "run services update atrium-api" "$FAKE_LOG" | grep -q "https://atrium-cup-2026.web.app,https://atrium-cup-2026.firebaseapp.com"'

[ "$FAILS" -eq 0 ] && echo "all script tests passed" || { echo "$FAILS script test(s) failed"; exit 1; }
