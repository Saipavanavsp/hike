# Runbook: deployment and post-deploy verification

## Topology

| Component | Local (Docker Compose) | Render, free (`render.yaml`) | Render, production (`deploy/render-production.yaml`) |
|---|---|---|---|
| Web (static SPA, CSP) | `frontend` (nginx) | `hike-web` static site | `hike-web` static site |
| API | `backend` | `hike-api` (free) | `hike-api` (`1c-2g`, 2 processes) |
| Background worker | `worker` (Celery + beat) | none: `TASKS_EAGER=true` | `hike-worker` (`0.5c-512mb`) |
| PostgreSQL 16 + pgvector | `postgres` | free (expires after 30 days, no backups) | `0.5c-1g` with daily backups and point-in-time recovery |
| Redis | `redis` | Key Value free | Key Value `256mb`, `noeviction` (it holds the task queue) |
| Resume files | `uploads` volume, or S3 with `--profile s3` | container disk (lost on restart) | S3-compatible bucket (Cloudflare R2), encrypted by the app |
| Backups | `backup` service (daily `pg_dump`, verified) | none | Render's managed backups |

Each component is a separate service, deployed and restarted independently. The API and the
worker share `JWT_SECRET` and `FILE_ENCRYPTION_KEY` through the `hike-shared` environment
group, so the worker can decrypt the files the API stored.

## Persistent encrypted resume storage

Resumes are encrypted (Fernet) by the app before they reach storage, so the bucket only ever
holds ciphertext. For production:

1. Create a Cloudflare R2 bucket (for example `hike-resumes`) and an API token with
   *Object Read & Write* on that bucket only.
2. Set on both `hike-api` and `hike-worker`: `S3_BUCKET`, `S3_ENDPOINT_URL`
   (`https://<account-id>.r2.cloudflarestorage.com`), `S3_ACCESS_KEY_ID`,
   `S3_SECRET_ACCESS_KEY`. The production blueprint prompts for them.
3. Back up `FILE_ENCRYPTION_KEY` somewhere safe (a password manager). Without it, the files
   cannot be decrypted.

Verified locally with an S3-compatible server (`docker compose --profile s3`, Adobe
S3Mock): the object for an uploaded resume is
`resumes/119/24c8cadbbef642a3b4dcbf1b43acb9f8.pdf`, 3,244 bytes, beginning with the
`HIKEENC1` header; the PDF content does not appear in it.

## Deploy

- CI (`.github/workflows/deploy.yml`), on every push to `main`: build the whole stack,
  run the Playwright suite, back up and verify a restore, then call the Render deploy hooks
  (`RENDER_DEPLOY_HOOK_API`, `RENDER_DEPLOY_HOOK_WEB`) and, if `SMOKE_URL` is set, smoke-test
  the live site.
- Migrations run on API start (`alembic upgrade head` in `scripts/start.sh`). They add
  tables, columns and indexes or relax constraints, so the previous release keeps working
  against the migrated schema during a deploy or after a rollback.
- Graceful shutdown: the API finishes in-flight requests (25 s); the worker finishes its
  current tasks (warm shutdown) and unfinished ones are redelivered.

## Post-deploy verification: the smoke test

```powershell
node e2e/tools/smoke.cjs https://hike-web.onrender.com
# reuse an account to prove data survived a restart/redeploy:
$env:SMOKE_EMAIL = "smoke-...@example.com"; node e2e/tools/smoke.cjs http://localhost:8080
```

It checks: API health (database and Redis), the CSP header, search with typo correction,
seeker registration or sign-in, a resume uploaded before the restart still decrypting to the
original bytes (with `SMOKE_EMAIL`), a new upload parsed by the worker, the signed download
matching the upload byte for byte, the match breakdown, the recruiter pipeline, the admin
System page, and access control. It exits non-zero at the first failure.

## Restart and redeploy test (2026-11-02, local stack, S3 storage)

1. `docker compose --profile s3 up` with `STORAGE_BACKEND=s3`; smoke test passed (10 checks),
   creating `smoke-mvz61yks@example.com` with resume 555.
2. `docker compose --profile s3 restart` (every container): smoke test with that account
   passed (11 checks): `resume 555 ... decrypts to the original`, new resume 556 parsed.
3. Redeploy: `docker compose --profile s3 up -d --build --force-recreate` (new images, new
   containers): passed again (11 checks), resume 555 still readable, resume 557 parsed.

Found and fixed during this test: after the backend container was recreated, nginx returned
502 because it had resolved `backend` to the old container IP at start-up. `nginx.conf` now
resolves the upstream at request time through Docker's DNS (`resolver 127.0.0.11`).

## Rollback

- Render: *Manual Deploy > Rollback* to the previous deploy in the service's Events tab.
  The previous version runs against the migrated database (see Deploy).
- Data: restore a backup (see [backup-restore.md](backup-restore.md)).

## What still needs your accounts

These steps need logins I do not have; everything above them was tested locally.

1. Render: create the Blueprint (free: `render.yaml`; production: Blueprint path
   `deploy/render-production.yaml`, which needs paid plans).
2. Cloudflare R2 (production storage): bucket and API token, values entered when Render
   prompts.
3. GitHub secrets: `RENDER_DEPLOY_HOOK_API`, `RENDER_DEPLOY_HOOK_WEB`, `SMOKE_URL`.
