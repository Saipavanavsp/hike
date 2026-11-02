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

## Live deployment (free plan)

Created on 2026-11-02 through the Render API, with the same settings as `render.yaml`:

| Service | Address / id |
|---|---|
| Website | https://hike-web-a3qk.onrender.com (`srv-dbk973vb9u1s7380jq7g`) |
| API | https://hike-api.onrender.com (`srv-dbk96vhsrm7s73e8i5m0`) |
| PostgreSQL 16 (free, expires 2026-12-02) | `dpg-dbk96dutlv9c73f7k9b0-a` |
| Key Value (free) | `red-dbk96eqjnfac739vdclg` |

Both services use `autoDeployTrigger: checksPass`: Render deploys `main` itself once the
GitHub checks pass. `.github/workflows/live-smoke.yml` smoke-tests the live site twice a day
(`SMOKE_URL` secret).

First deploy findings, fixed: the 512 MB instance ran out of memory while seeding (embedding
all job windows in one batch, 587 MB peak); embeddings now run in batches of 4 (373 MB),
the seed stores the committed evaluation instead of recomputing it, and a seed killed
part-way is detected and restarted on the next start.

Smoke test against the live site after the fix: 10 of 10 checks passed; console sweep: 18
pages, no errors.

**Before 2026-12-02:** Render deletes free databases after 30 days. Upgrade `hike-db` to a
paid plan, or create a new free database and update `DATABASE_URL` (the API reseeds itself).

## Production upgrade (needs paid plans and a Cloudflare account)

Use `deploy/render-production.yaml` (Blueprint path) for a separate worker, a backed-up
database and R2 storage; see "Persistent encrypted resume storage" above.