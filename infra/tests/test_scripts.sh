#!/usr/bin/env bash
# Runs setup_gcp.sh and deploy.sh against fake gcloud/firebase binaries and checks what they would do.
# Usage: bash infra/tests/test_scripts.sh      (no cloud access needed; exit 0 = all pass)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/bin"
export FAKE_LOG="$WORK/calls.log"

cat > "$WORK/bin/gcloud" <<'FAKE'
#!/usr/bin/env bash
echo "gcloud $*" >> "$FAKE_LOG"
case "$*" in *"--data-file=-"*) cat >/dev/null ;; esac
case "$*" in "run deploy atrium-web"*) touch "$FAKE_LOG.web" ;; esac
case "$*" in
  "auth list"*) echo "tester@example.test" ;;
  *"sql instances describe"*"connectionName"*) echo "proj:us-central1:atrium-db" ;;
  *"sql users list"*) echo "postgres" ;;
  *"run services describe atrium-web"*"run.googleapis.com/urls"*)
    { [ -n "${FAKE_WEB_EXISTS:-}" ] || [ -f "$FAKE_LOG.web" ]; } \
      && echo '["https://atrium-web-123.us-central1.run.app","https://atrium-web-test.a.run.app"]' || exit 1 ;;
  *"run services describe atrium-web"*) { [ -n "${FAKE_WEB_EXISTS:-}" ] || [ -f "$FAKE_LOG.web" ]; } && echo "https://atrium-web-test.a.run.app" || exit 1 ;;
  *"run services describe atrium-api"*) echo "https://atrium-api-test.a.run.app" ;;
  "projects describe"*) exit 0 ;;
  *" describe "*) exit 1 ;;
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

echo "deploy.sh when the web service already exists"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web"
FAKE_WEB_EXISTS=1 bash infra/deploy.sh > "$WORK/deploy.out" 2>&1
STATUS=$?
API_DEPLOY="$(grep -m1 "run deploy atrium-api" "$FAKE_LOG")"
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "API deploy keeps CORS for the live web origin" 'echo "$API_DEPLOY" | grep -q "CORS_ORIGINS=.*https://atrium-web-test.a.run.app"'
check "API deploy allows both Cloud Run URLs of the web service" 'echo "$API_DEPLOY" | grep -q "https://atrium-web-123.us-central1.run.app"'

echo "deploy.sh on the very first release"
: > "$FAKE_LOG"; rm -f "$FAKE_LOG.web"
bash infra/deploy.sh > "$WORK/deploy1.out" 2>&1
STATUS=$?
check "exits 0 (was $STATUS)" '[ "$STATUS" -eq 0 ]'
check "sets CORS after the web service exists" 'grep "run services update atrium-api" "$FAKE_LOG" | grep -q "CORS_ORIGINS="'
check "first-release CORS allows both Cloud Run URLs" 'grep "run services update atrium-api" "$FAKE_LOG" | grep -q "https://atrium-web-123.us-central1.run.app"'

[ "$FAILS" -eq 0 ] && echo "all script tests passed" || { echo "$FAILS script test(s) failed"; exit 1; }
