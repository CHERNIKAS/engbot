#!/usr/bin/env bash
# Throwaway environment for tests/e2e.
#
#   ops/e2e.sh up     Postgres + Redis on localhost, loaded with a copy of
#                     production and migrated to this tree's schema
#   ops/e2e.sh test   run tests/e2e against it (extra args go to pytest)
#   ops/e2e.sh down   remove both containers — the copy holds learners' data
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.prod.yml"
PG=eng-e2e-pg
RD=eng-e2e-redis
PG_PORT=55481
RD_PORT=55482
export E2E_DATABASE_URL="postgresql+asyncpg://englsh:e2e@127.0.0.1:${PG_PORT}/pristine"
export E2E_REDIS_URL="redis://127.0.0.1:${RD_PORT}/0"

down() { docker rm -f "$PG" "$RD" >/dev/null 2>&1 || true; }

up() {
  down
  docker run -d --name "$PG" --cpus 1 -e POSTGRES_USER=englsh -e POSTGRES_PASSWORD=e2e \
    -e POSTGRES_DB=postgres -p "127.0.0.1:${PG_PORT}:5432" postgres:16-alpine >/dev/null
  docker run -d --name "$RD" --cpus 0.5 -p "127.0.0.1:${RD_PORT}:6379" redis:7-alpine >/dev/null
  # Over TCP: on first start the image runs a socket-only server for initdb,
  # reports ready, then restarts — a socket check can land in that gap.
  for _ in $(seq 1 30); do docker exec "$PG" pg_isready -h 127.0.0.1 -U englsh >/dev/null 2>&1 && break; sleep 1; done
  docker exec "$PG" createdb -U englsh pristine
  $COMPOSE exec -T postgres pg_dump -U englsh englsh | docker exec -i "$PG" psql -q -U englsh -d pristine >/dev/null
  # The copy is at production's schema; the tree under test may add migrations.
  if ! DATABASE_URL="$E2E_DATABASE_URL" REDIS_URL="$E2E_REDIS_URL" .venv/bin/alembic upgrade head > /tmp/englshbot-e2e-migrate.log 2>&1; then
    tail -5 /tmp/englshbot-e2e-migrate.log
    echo "!! migrations failed on the copy — full log: /tmp/englshbot-e2e-migrate.log"
    exit 1
  fi
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  test) shift; .venv/bin/pytest -q -p no:cacheprovider tests/e2e "$@" ;;
  *) echo "usage: ops/e2e.sh up|test|down"; exit 2 ;;
esac
