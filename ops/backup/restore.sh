#!/bin/sh
# Restore a dump into a database.
#   sh /scripts/restore.sh /backups/hike-20261102T040000Z.dump hike_restored
#   sh /scripts/restore.sh latest hike            # disaster recovery: replace the live DB
# Replacing the live database: stop backend and worker first (docker compose stop backend worker).
set -eu

file="$1"
target="${2:?target database name required}"
if [ "$file" = "latest" ]; then
  file="$(ls -1t "${BACKUP_DIR:-/backups}"/hike-*.dump | head -n 1)"
fi
[ -f "$file" ] || { echo "no such dump: $file" >&2; exit 1; }
if [ -f "$file.sha256" ]; then
  sha256sum -c "$file.sha256" > /dev/null
fi

psql -v ON_ERROR_STOP=1 -d postgres -c "DROP DATABASE IF EXISTS \"$target\" WITH (FORCE)"
psql -v ON_ERROR_STOP=1 -d postgres -c "CREATE DATABASE \"$target\""
pg_restore --no-owner --exit-on-error --dbname="$target" "$file"
echo "{\"event\": \"restore_done\", \"file\": \"$file\", \"database\": \"$target\"}"
