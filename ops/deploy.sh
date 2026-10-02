#!/usr/bin/env bash
# Deploy the bot — but only if the tests pass first.
#
#   ops/deploy.sh          unit tests → e2e tests → DB backup → build → restart → health check
#   ops/deploy.sh --check  the tests only; nothing on the live bot is touched
#
# The e2e step needs a database, so it brings up a throwaway Postgres + Redis
# (localhost only), loads a copy of production into it, applies this tree's
# migrations, runs tests/e2e, and removes both containers on exit — whatever
# happens. Written after 2026-10-02, when four card bugs reached learners
# through a suite that had no database in it at all.
set -euo pipefail
cd "$(dirname "$0")/.."

CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

COMPOSE="docker compose -f docker-compose.prod.yml"

trap 'ops/e2e.sh down' EXIT
step() { printf '\n== %s\n' "$*"; }

step "unit tests"
.venv/bin/pytest -q -x --ignore=tests/e2e

step "e2e: throwaway Postgres + Redis with a copy of production"
ops/e2e.sh up

step "e2e tests"
if ! ops/e2e.sh test -x > /tmp/englshbot-e2e.log 2>&1; then
  grep -E "^(FAILED|ERROR) |^E  |passed|failed" /tmp/englshbot-e2e.log | head -20
  echo "!! e2e tests failed — not deploying. Full log: /tmp/englshbot-e2e.log"
  echo "   Reproduce: ops/e2e.sh up && ops/e2e.sh test -k <name>; ops/e2e.sh down"
  exit 1
fi
grep -E "passed" /tmp/englshbot-e2e.log | tail -1
ops/e2e.sh down

if [[ $CHECK_ONLY == 1 ]]; then
  step "check only: all green, nothing deployed"
  exit 0
fi

step "backup"
STAMP=$(date +%Y%m%d-%H%M%S)
$COMPOSE exec -T postgres pg_dump -U englsh englsh | gzip > "backups/englsh-predeploy-${STAMP}.sql.gz"
gzip -t "backups/englsh-predeploy-${STAMP}.sql.gz"
echo "backups/englsh-predeploy-${STAMP}.sql.gz"

step "build + restart"
STARTED=$(date -u +%Y-%m-%dT%H:%M:%S)
$COMPOSE build bot | tail -1
$COMPOSE up -d bot | tail -1

step "health"
for _ in $(seq 1 30); do
  docker logs --since "$STARTED" englshbot-bot-1 2>&1 | grep -q "Run polling" && break
  sleep 2
done
if ! docker logs --since "$STARTED" englshbot-bot-1 2>&1 | grep -q "Run polling"; then
  echo "!! the bot did not start polling — check: docker logs englshbot-bot-1"; exit 1
fi
if docker logs --since "$STARTED" englshbot-bot-1 2>&1 | grep -qE "Traceback|\"level\":\"error\""; then
  echo "!! errors in the log since start:"; docker logs --since "$STARTED" englshbot-bot-1 2>&1 | grep -E "Traceback|\"level\":\"error\"" | head -5
  exit 1
fi
echo "bot is polling, no errors. Commit and push if you have not."
