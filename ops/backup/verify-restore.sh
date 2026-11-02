#!/bin/sh
# Restore test: take a fresh backup, restore it into a scratch database, and compare the
# exact row count of every table and the latest Alembic revision with the live database.
# Exits non-zero on any difference. Run regularly: a backup is only as good as its restore.
#   docker compose exec backup sh /scripts/verify-restore.sh
set -eu

SCRATCH="hike_restore_check"
sh /scripts/backup.sh > /dev/null
latest="$(ls -1t "${BACKUP_DIR:-/backups}"/hike-*.dump | head -n 1)"
sh /scripts/restore.sh "$latest" "$SCRATCH" > /dev/null

counts() {
  psql -d "$1" -At -F ' ' -c "
    SELECT table_name, (xpath('/row/n/text()',
      query_to_xml(format('SELECT count(*) AS n FROM %I', table_name), false, true, '')))[1]::text
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    ORDER BY table_name"
}

counts "$PGDATABASE" > /tmp/live.txt
counts "$SCRATCH" > /tmp/restored.txt
live_rev="$(psql -d "$PGDATABASE" -At -c 'SELECT version_num FROM alembic_version')"
restored_rev="$(psql -d "$SCRATCH" -At -c 'SELECT version_num FROM alembic_version')"
vector="$(psql -d "$SCRATCH" -At -c "SELECT count(*) FROM jobs WHERE embedding IS NOT NULL")"

echo "dump:            $latest"
echo "tables:          $(wc -l < /tmp/live.txt)"
echo "alembic:         live=$live_rev restored=$restored_rev"
echo "job embeddings:  $vector restored (pgvector)"
status=0
if ! diff -u /tmp/live.txt /tmp/restored.txt; then
  echo "ROW COUNTS DIFFER" >&2
  status=1
fi
[ "$live_rev" = "$restored_rev" ] || { echo "REVISION DIFFERS" >&2; status=1; }
echo "rows per table (live = restored):"
sed 's/^/  /' /tmp/restored.txt
psql -d postgres -q -c "DROP DATABASE \"$SCRATCH\" WITH (FORCE)"
[ "$status" -eq 0 ] && echo "RESTORE VERIFIED"
exit "$status"
