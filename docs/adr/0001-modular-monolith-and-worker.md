# 0001. One FastAPI service plus one Celery worker, not microservices

**Status:** Accepted

## Context
Hike has search, resumes, matching, applications, interviews, notifications and admin. One
developer builds and runs it; traffic is small; most features share the same data (a match
score needs the resume, the job and the seeker profile together).

## Decision
A single FastAPI application organised by module (`api/`, `services/`, `ml/`, `models/`),
one PostgreSQL database, and one Celery worker process for slow or failure-prone work. The
worker runs the same code base and image as the API.

## Consequences
- Transactions span features (an application and its first status-history row commit
  together); no distributed transactions, no service-to-service auth, one deploy.
- Module boundaries are enforced by convention, not by the network. A service could be
  split out later along the existing `services/` seams (the worker is the first split).
- The API and the worker both load the embedding model (about 90 MB each).
- Scaling is horizontal on the whole API (`WEB_CONCURRENCY`, more instances), not per
  feature. The load test shows the API process is the first bottleneck (docs/load-testing.md).

## Alternatives considered
- **Microservices** (search, resumes, matching, notifications): independent scaling and
  deploys, at the cost of network calls in every request, data duplication or chatty
  APIs, and operational work that a project of this size does not need.
- **No worker** (FastAPI `BackgroundTasks`): simpler, but work is lost on restart, there
  are no retries, and a slow parse competes with requests for the same process.
