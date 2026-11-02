#!/bin/sh
# One PostgreSQL backup: custom-format pg_dump, checked with pg_restore --list, then old
# dumps beyond BACKUP_KEEP_DAYS are deleted. Uses the standard PG* environment variables.
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
mkdir -p "$BACKUP_DIR"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp="$BACKUP_DIR/.hike-$stamp.dump.partial"
out="$BACKUP_DIR/hike-$stamp.dump"

pg_dump --format=custom --compress=6 --no-owner --file="$tmp"
# A dump that pg_restore cannot list is corrupt: never let it replace a good one.
pg_restore --list "$tmp" > /dev/null
mv "$tmp" "$out"
sha256sum "$out" > "$out.sha256"

find "$BACKUP_DIR" -name 'hike-*.dump' -mtime "+$KEEP_DAYS" -exec rm -f {} {}.sha256 \;
size="$(du -h "$out" | cut -f1)"
echo "{\"event\": \"backup_written\", \"file\": \"$out\", \"size\": \"$size\"}"
