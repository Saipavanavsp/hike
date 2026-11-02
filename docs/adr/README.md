# Architecture Decision Records

Short records of the decisions that shape Hike: the context, what was decided, and what it costs.
Format: [Michael Nygard's ADR template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

| # | Decision | Status |
|---|---|---|
| [0001](0001-modular-monolith-and-worker.md) | One FastAPI service plus one Celery worker, not microservices | Accepted |
| [0002](0002-postgres-for-search-and-vectors.md) | PostgreSQL full-text search and pgvector instead of Elasticsearch or a vector database | Accepted |
| [0003](0003-onnx-runtime-for-embeddings.md) | MiniLM through ONNX Runtime in production, sentence-transformers as the reference | Accepted |
| [0004](0004-celery-with-tracked-tasks.md) | Celery on Redis, with a task table for status, retries and dead letters | Accepted |
| [0005](0005-jwt-with-rotating-refresh-cookie.md) | Short-lived JWT in memory plus a rotating refresh token in an httpOnly cookie | Accepted |
| [0006](0006-resume-storage-and-access.md) | Encrypt resumes before storage; serve them through short-lived signed links | Accepted |
| [0007](0007-identity-redaction-before-embedding.md) | Remove names, contacts and institutions before embedding | Accepted |
| [0008](0008-load-shedding.md) | Cap concurrent requests and shed load with 503 instead of queueing without bound | Accepted |
