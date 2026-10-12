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
  "projects describe"*) exit 0 ;;
  *" describe "*) [ -n "${FAKE_EXISTING:-}" ] && exit 0 || exit 1 ;;
esac
exit 0
FAKE
printf '#!/usr/bin/env bash\nexit 1\n' > "$WORK/bin/firebase"
chmod +x "$WORK/bin/gcloud" "$WORK/bin/firebase"
export PATH="$WORK/bin:$PATH"

FAILS=0
check() { if eval "$2"; then printf '  pass %s\n' "$1"; else printf '  FAIL %s\n' "$1"; FAILS=$((FAILS + 1)); fi; }
cd "$ROOT"

echo "setup_gcp.sh on an empty project"
: > "$FAKE_LOG"
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

echo "setup_gcp.sh rerun on a project that is already set up"
: > "$FAKE_LOG"
FAKE_EXISTING=1 BILLING_ACCOUNT=TEST-BILLING bash infra/setup_gcp.sh > "$WORK/setup2.out" 2>&1
STATUS=$?
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "does not re-link billing (fails at the billing project quota)" '! grep -q "billing projects link" "$FAKE_LOG"'
check "turns on backups for an existing database without them" 'grep -q "sql instances patch atrium-db.*--backup-start-time" "$FAKE_LOG"'
check "leaves the live database password alone" '! grep -q "sql users set-password" "$FAKE_LOG"'
check "does not add a new secret version" '! grep -q "secrets versions add" "$FAKE_LOG"'
check "does not create a second budget" '! grep -q "billing budgets create" "$FAKE_LOG"'

echo "deploy.sh when the web service already exists"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web"
FAKE_WEB_EXISTS=1 bash infra/deploy.sh > "$WORK/deploy.out" 2>&1
STATUS=$?
API_DEPLOY="$(grep -m1 "run deploy atrium-api" "$FAKE_LOG")"
WEB_DEPLOY="$(grep -m1 "run deploy atrium-web" "$FAKE_LOG")"
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "API deploy keeps CORS for the live web origin" 'echo "$API_DEPLOY" | grep -q "CORS_ORIGINS=.*https://atrium-web-test.a.run.app"'
check "API deploy allows both Cloud Run URLs of the web service" 'echo "$API_DEPLOY" | grep -q "https://atrium-web-123.us-central1.run.app"'
check "API env values reach gcloud unmangled" 'echo "$API_DEPLOY" | grep -q "MARKET_CACHE_DIR=/tmp/cache@" && echo "$API_DEPLOY" | grep -q "CORS_ORIGINS=https://atrium-web-123.us-central1.run.app,"'
check "API scales to zero by default" 'echo "$API_DEPLOY" | grep -q -- "--min-instances 0"'
check "web scales to zero by default" 'echo "$WEB_DEPLOY" | grep -q -- "--min-instances 0"'
check "both services use startup CPU boost" 'echo "$API_DEPLOY" | grep -q -- "--cpu-boost" && echo "$WEB_DEPLOY" | grep -q -- "--cpu-boost"'

echo "deploy.sh with warm instances for the judging window"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web"
FAKE_WEB_EXISTS=1 API_MIN_INSTANCES=1 WEB_MIN_INSTANCES=1 bash infra/deploy.sh > "$WORK/deploy-warm.out" 2>&1
check "API keeps one warm instance" 'grep -m1 "run deploy atrium-api" "$FAKE_LOG" | grep -q -- "--min-instances 1"'
check "web keeps one warm instance" 'grep -m1 "run deploy atrium-web" "$FAKE_LOG" | grep -q -- "--min-instances 1"'

echo "deploy.sh on the very first release"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web"
bash infra/deploy.sh > "$WORK/deploy1.out" 2>&1
STATUS=$?
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "sets CORS after the web service exists" 'grep "run services update atrium-api" "$FAKE_LOG" | grep -q "CORS_ORIGINS="'
check "first-release CORS allows both Cloud Run URLs" 'grep "run services update atrium-api" "$FAKE_LOG" | grep -q "https://atrium-web-123.us-central1.run.app"'

[ "$FAILS" -eq 0 ] && echo "all script tests passed" || { echo "$FAILS script test(s) failed"; exit 1; }
