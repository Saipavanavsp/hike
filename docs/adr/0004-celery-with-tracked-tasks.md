# 0004. Celery on Redis, with a task table for status, retries and dead letters

**Status:** Accepted

## Context
Resume parsing (untrusted files), embeddings, bulk re-scoring, email and retention are
slow or can fail. Users need to see progress ("processing" resumes), operators need to see
failures, and failed work must be retryable.

## Decision
Celery with Redis as the broker (Redis is already used for caching and rate limits).
Every task also has a row in `background_tasks` (queued, running, retrying, succeeded,
rejected, failed; attempts; error). A small `tracked` decorator adds exponential backoff
with jitter, `PermanentError` for bad input ("rejected", no alert), admin alerts on final
failure, a dead-letter list with an admin retry, and recovery of tasks left behind by a
dead worker. `acks_late` plus idempotent tasks (row locks, stable email Message-ID) make
redelivery safe. `TASKS_EAGER=true` runs tasks inline where no worker exists.

## Consequences
- Task status is queryable with SQL and shown in the UI; Celery's result backend is not used.
- Every task must be idempotent; this is tested for each one.
- One more process to run and monitor (heartbeat, `hike_worker_up`, queue depth).
- Redis is a single point of failure for queueing; if it is down, `enqueue` runs the task
  inline rather than losing it.

## Alternatives considered
- **RQ / arq**: simpler, but no beat scheduler (RQ) or an async-only model (arq) that does
  not fit the sync SQLAlchemy code.
- **PostgreSQL as the queue** (`SKIP LOCKED`): one fewer moving part; would need its own
  scheduler, retry and worker code.
