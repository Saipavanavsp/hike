#!/bin/sh
# Runs backup.sh once at start, then every BACKUP_INTERVAL_SECONDS (default: daily).
# A failed backup is logged and retried at the next interval; the container keeps running.
set -u
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
until pg_isready -q; do sleep 2; done
while true; do
  if ! sh /scripts/backup.sh; then
    echo '{"event": "backup_failed", "alert": true}'
  fi
  sleep "$INTERVAL"
done
