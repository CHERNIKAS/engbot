#!/usr/bin/env bash
# Restore — and, by default, only *rehearse* a restore.
#
# A backup nobody has restored is a guess. This runs the real thing against a
# scratch database and compares it to the live one, so the answer is a fact.
#
#   Rehearse (safe, the default):
#       bash scripts/restore.sh
#       bash scripts/restore.sh /opt/englshbot/backups/englsh-20260905-041701.sql.gz
#
#   Restore for real, over the live database — destroys current data:
#       bash scripts/restore.sh --into-live <dump>
#
# The live path is deliberately awkward. The old instructions were a one-liner
# piping a dump straight into `-d englsh`; pasted in a hurry that is how a bad
# night becomes a worse one.
#
# Env overrides: PG_CONTAINER, PG_USER, PG_DB, SCRATCH_DB, BACKUP_DIR.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/englshbot/backups}"
PG_CONTAINER="${PG_CONTAINER:-englshbot-postgres-1}"
PG_USER="${PG_USER:-englsh}"
PG_DB="${PG_DB:-englsh}"
SCRATCH_DB="${SCRATCH_DB:-englsh_restore_check}"

INTO_LIVE=0
if [ "${1:-}" = "--into-live" ]; then
    INTO_LIVE=1
    shift
fi

DUMP="${1:-}"
if [ -z "$DUMP" ]; then
    DUMP="$(ls -t "$BACKUP_DIR"/englsh-*.sql.gz 2>/dev/null | head -1 || true)"
fi
if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
    echo "restore.sh: no dump found (looked in $BACKUP_DIR)" >&2
    exit 1
fi

psql_in() { docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$1"; }
psql_q() { docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$1" -t -A -c "$2"; }

# Row counts that would make a silent partial restore obvious.
counts_sql="
select 'alembic=' || coalesce((select version_num from alembic_version), '?')
union all select 'users=' || count(*) from users
union all select 'words=' || count(*) from words
union all select 'user_words=' || count(*) from user_words
union all select 'word_reviews=' || count(*) from word_reviews
order by 1;"

if [ "$INTO_LIVE" = "1" ]; then
    echo "restore.sh: about to OVERWRITE $PG_DB from $DUMP"
    echo "restore.sh: current contents:"
    psql_q "$PG_DB" "$counts_sql" | sed 's/^/    /'
    printf 'Type the database name to confirm: '
    read -r confirm
    if [ "$confirm" != "$PG_DB" ]; then
        echo "restore.sh: aborted" >&2
        exit 1
    fi
    gunzip -c "$DUMP" | psql_in "$PG_DB" >/dev/null
    echo "restore.sh: restored. now:"
    psql_q "$PG_DB" "$counts_sql" | sed 's/^/    /'
    exit 0
fi

echo "restore.sh: rehearsing $DUMP into $SCRATCH_DB (live database untouched)"
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -q \
    -c "DROP DATABASE IF EXISTS $SCRATCH_DB;" \
    -c "CREATE DATABASE $SCRATCH_DB OWNER $PG_USER;" >/dev/null

errors="$(mktemp)"
trap 'rm -f "$errors"' EXIT
gunzip -c "$DUMP" | psql_in "$SCRATCH_DB" 2>"$errors" >/dev/null

# The dump carries --clean, so DROPs of absent objects are expected on an empty
# database. Anything else is a real failure.
real_errors="$(grep '^ERROR' "$errors" | grep -v 'does not exist' || true)"
if [ -n "$real_errors" ]; then
    echo "restore.sh: RESTORE FAILED" >&2
    echo "$real_errors" | head -20 >&2
    exit 1
fi

live="$(psql_q "$PG_DB" "$counts_sql")"
restored="$(psql_q "$SCRATCH_DB" "$counts_sql")"

echo "  live:     $(echo "$live" | tr '\n' ' ')"
echo "  restored: $(echo "$restored" | tr '\n' ' ')"

docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -q \
    -c "DROP DATABASE $SCRATCH_DB;" >/dev/null

if [ "$live" = "$restored" ]; then
    echo "restore.sh: OK — the dump restores to an identical database"
else
    # Not automatically a failure: the dump is from 04:17 and the live database
    # has moved on since. Differences in review counts are expected; a missing
    # table or a zeroed count is not.
    echo "restore.sh: counts differ — expected if the dump predates recent activity."
    echo "restore.sh: check that every table is present and nothing is zero."
fi
