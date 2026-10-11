#!/usr/bin/env bash
# Checks everything deploy.sh needs. Exit 0 means go.
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-atrium-cup-2026}"
ok() { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; exit 1; }

command -v gcloud >/dev/null || fail "gcloud not installed"
ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1)"
[ -n "$ACCOUNT" ] || fail "no active gcloud account (run: gcloud auth login)"
ok "gcloud authenticated as $ACCOUNT"
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then ok "project $PROJECT_ID exists"
else printf '  warn project %s missing (setup_gcp.sh creates it)\n' "$PROJECT_ID"; fi
[ -f services/api/Dockerfile ] && ok "api Dockerfile" || fail "services/api/Dockerfile missing"
[ -f apps/web/Dockerfile ] && ok "web Dockerfile" || fail "apps/web/Dockerfile missing"
[ -f services/api/uv.lock ] && ok "uv.lock present" || fail "run: cd services/api && uv lock"
[ -f apps/web/pnpm-lock.yaml ] && ok "pnpm-lock present" || fail "run: cd apps/web && pnpm install"

# Forbidden words live in an untracked file (one per line) so the public repo never spells them out.
if [ -f infra/.forbidden-words ]; then
  while IFS= read -r WORD; do
    [ -z "$WORD" ] && continue
    if grep -rqi --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git \
         --exclude-dir=.next --exclude-dir=.superpowers --exclude=.forbidden-words -e "$WORD" .; then
      fail "a forbidden word from infra/.forbidden-words is in the tree"
    fi
  done < infra/.forbidden-words
  ok "forbidden words absent"
else
  printf '  warn infra/.forbidden-words missing; create it (gitignored), one word per line\n'
fi
echo "preflight passed"
