#!/usr/bin/env bash
# Daily Postgres backup for Lazy Bot.
#
# Dumps the englshbot Postgres container to a gzip'd SQL file and prunes old
# ones. Install on the prod host and run from cron (see scripts/install-backup-cron.sh).
#
#   Manual run:   bash /opt/englshbot/scripts/backup.sh
#   Restore:      gunzip -c <dump>.sql.gz | docker exec -i englshbot-postgres-1 \
#                     psql -U englsh -d englsh
#
# Env overrides: BACKUP_DIR, RETENTION_DAYS, PG_CONTAINER, PG_USER, PG_DB.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/englshbot/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
PG_CONTAINER="${PG_CONTAINER:-englshbot-postgres-1}"
PG_USER="${PG_USER:-englsh}"
PG_DB="${PG_DB:-englsh}"

mkdir -p "$BACKUP_DIR"
stamp="$(date +%Y%m%d-%H%M%S)"
out="$BACKUP_DIR/englsh-$stamp.sql.gz"

# --clean --if-exists so the dump restores cleanly over an existing schema.
docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" --clean --if-exists \
    | gzip > "$out"

# Fail loudly if the dump is suspiciously small (empty/failed dump).
size="$(stat -c%s "$out" 2>/dev/null || echo 0)"
if [ "$size" -lt 1024 ]; then
    echo "backup.sh: dump too small ($size bytes) — aborting, keeping older backups" >&2
    rm -f "$out"
    exit 1
fi

# Retention: drop dumps older than RETENTION_DAYS.
find "$BACKUP_DIR" -name 'englsh-*.sql.gz' -type f -mtime "+$RETENTION_DAYS" -delete

echo "backup.sh: wrote $out ($size bytes); kept last $RETENTION_DAYS days"
