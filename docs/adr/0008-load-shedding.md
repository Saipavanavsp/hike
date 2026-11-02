# 0008. Cap concurrent requests and shed load with 503 instead of queueing without bound

**Status:** Accepted

## Context
The 500-user load test deadlocked the API: FastAPI ran sync endpoints and the cleanup of
the sync session dependency in a 40-thread pool, the database pool had 15 connections,
and once all threads waited for a connection, the requests holding connections could not
get a thread to return them. The API stayed unresponsive after the test ended.

## Decision
- The session dependency is an async generator, so sessions close on the event loop.
- `ConcurrencyLimitMiddleware` lets at most `MAX_CONCURRENT_REQUESTS` (15) requests run at
  once. Others wait on the event loop, holding no thread or connection, and receive
  `503 Retry-After: 2` after `REQUEST_QUEUE_TIMEOUT` (10 s). Health checks and `/metrics`
  bypass the limit.
- The database pool (15 + 15 overflow) covers two sessions per running request, with a
  10-second pool timeout.

## Consequences
- 500 users: 218 req/s with 0 errors and p99 290 ms (5.9 req/s and 96% errors before).
- Under extreme overload clients see fast 503s instead of hangs; the frontend's normal
  error handling shows them. `hike_requests_shed_total` and `hike_requests_waiting` make
  it visible.
- Throughput per process is bounded by the limit; scaling means more processes or
  instances (`WEB_CONCURRENCY`), each with its own pool within PostgreSQL's limits.

## Alternatives considered
- **Bigger pools only**: moves the cliff, does not remove the deadlock.
- **Async SQLAlchemy throughout**: removes the thread pool from the request path, but is a
  rewrite of every service; the middleware fixes the failure mode now.
