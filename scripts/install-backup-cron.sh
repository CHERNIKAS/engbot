#!/usr/bin/env bash
# Install the daily backup cron on the prod host. Idempotent — safe to re-run.
# Runs scripts/backup.sh every day at 04:17 (server local time), logging to
# /opt/englshbot/backups/backup.log.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/englshbot}"
SCRIPT="$REPO_DIR/scripts/backup.sh"
LOG="$REPO_DIR/backups/backup.log"
LINE="17 4 * * * bash $SCRIPT >> $LOG 2>&1"

chmod +x "$SCRIPT"
mkdir -p "$REPO_DIR/backups"

# Replace any prior backup.sh cron line, keep everything else.
current="$(crontab -l 2>/dev/null | grep -v 'scripts/backup.sh' || true)"
printf '%s\n%s\n' "$current" "$LINE" | grep -v '^$' | crontab -

echo "installed cron:"
crontab -l | grep 'scripts/backup.sh'
