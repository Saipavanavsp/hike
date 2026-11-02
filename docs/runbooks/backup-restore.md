# Runbook: backups and restore

**What is backed up:** the PostgreSQL database (all tables, including pgvector embeddings
and the Alembic revision). **Not in the database dump:** resume files (object storage or
the `uploads` volume) and `FILE_ENCRYPTION_KEY`. Back up both separately; without the key,
restored resume files cannot be decrypted.

**Recovery objectives (this setup):** RPO 24 h (daily dumps), RTO about 10 minutes for a
database of this size.

## Automatic backups (Docker Compose)

The `backup` service runs `ops/backup/backup.sh` at start and then every
`BACKUP_INTERVAL_SECONDS` (default 86400):

1. `pg_dump --format=custom` to `/backups/.hike-<UTC time>.dump.partial`;
2. `pg_restore --list` on the file: a dump that cannot be listed is corrupt and is never
   kept;
3. rename to `hike-<UTC time>.dump`, write a `.sha256` checksum;
4. delete dumps older than `BACKUP_KEEP_DAYS` (default 7).

Logs are JSON lines: `{"event": "backup_written", ...}` or `{"event": "backup_failed", "alert": true}`.

```powershell
docker compose logs backup --tail 5
docker compose exec backup ls -lh /backups
```

On Render, use the managed database's backups (paid plans: daily snapshots with
point-in-time recovery) or run `backup.sh` as a cron job against `DATABASE_URL`.

## Verify a restore (do this regularly)

```powershell
docker compose exec backup sh /scripts/verify-restore.sh
```

It takes a fresh dump, restores it into a scratch database, and compares the exact row
count of every table and the Alembic revision with the live database, then drops the
scratch database. It exits non-zero on any difference. CI runs it on every push to `main`
(`.github/workflows/deploy.yml`). Output from 2026-11-02:

```
dump:            /backups/hike-20261102T044330Z.dump
tables:          18
alembic:         live=0008 restored=0008
job embeddings:  51 restored (pgvector)
rows per table (live = restored):
  alembic_version 1
  application_status_history 118
  applications 65
  audit_logs 44
  background_tasks 29
  ...
  users 38
RESTORE VERIFIED
```

## Disaster recovery: restore the live database

1. Stop everything that writes:
   ```powershell
   docker compose stop backend worker
   ```
2. Pick a dump (`latest`, or a file from `ls /backups`) and restore it over `hike`:
   ```powershell
   docker compose exec backup sh /scripts/restore.sh latest hike
   ```
   The checksum is verified first; the script drops and recreates the database.
3. Start the API (it runs `alembic upgrade head`, so an older dump is migrated forward) and
   the worker:
   ```powershell
   docker compose start backend worker
   ```
4. Check: `curl http://localhost:8000/health`, sign in, open a resume (proves the encryption
   key matches the restored files), and run `node e2e/tools/smoke.cjs` (see the deployment
   runbook).
5. Background tasks that were queued after the dump are gone with it: users re-upload
   resumes that show as processing, and admins can retry dead-lettered tasks.

## Restore into a separate database (inspect without touching live data)

```powershell
docker compose exec backup sh /scripts/restore.sh /backups/hike-20261102T044330Z.dump hike_inspect
docker compose exec postgres psql -U hike -d hike_inspect
```
