# Architecture

System overview: see the diagram in the [README](../README.md#architecture). Decisions and
their trade-offs: [docs/adr](adr/README.md). Threats and mitigations: [threat-model.md](threat-model.md).

- [Database (ER diagram)](#database)
- [Sign-in, refresh rotation and theft detection](#sign-in-refresh-rotation-and-theft-detection)
- [Resume upload and processing](#resume-upload-and-processing)
- [Search](#search)
- [Applying, notifications and email](#applying-notifications-and-email)
- [Interview scheduling](#interview-scheduling)
- [Request path inside the API](#request-path-inside-the-api)

## Database

PostgreSQL 16 with `pgvector`, `pg_trgm`, `fuzzystrmatch` and `citext`. Migrations:
`backend/alembic/versions` (0001-0009). Key columns only.

```mermaid
erDiagram
    users ||--o| seeker_profiles : has
    users ||--o| recruiter_profiles : has
    companies ||--o{ recruiter_profiles : employs
    users ||--o{ refresh_tokens : "signs in with"
    users ||--o{ resumes : uploads
    companies ||--o{ jobs : posts
    users ||--o{ jobs : "recruits for"
    users ||--o{ saved_jobs : saves
    jobs ||--o{ saved_jobs : "saved as"
    jobs ||--o{ applications : receives
    users ||--o{ applications : "applies with"
    resumes |o--o{ applications : "attached to (NULL if deleted)"
    applications ||--o{ application_status_history : "moves through"
    applications ||--o{ interviews : schedules
    resumes ||--o{ match_scores : scored
    jobs ||--o{ match_scores : scored
    users ||--o{ notifications : receives
    users ||--o{ saved_searches : saves
    users |o--o{ background_tasks : "owns (NULL if deleted)"
    users |o--o{ audit_logs : "acted (NULL if deleted)"

    users {
        bigint id PK
        citext email UK
        text password_hash "bcrypt"
        enum role "seeker | recruiter | admin"
        bool is_active
        bool email_notifications
        timestamptz last_login_at
    }
    refresh_tokens {
        uuid id PK "JWT jti"
        uuid family_id "rotation family"
        varchar token_hash "sha256"
        timestamptz expires_at
        timestamptz revoked_at
    }
    seeker_profiles {
        bigint user_id PK, FK
        varchar current_location
        varchar_array preferred_locations
        bool open_to_remote
        numeric years_experience
        varchar phone "private"
    }
    recruiter_profiles {
        bigint user_id PK, FK
        bigint company_id FK
    }
    companies {
        bigint id PK
        varchar name UK
        varchar slug UK
        varchar website
        varchar industry
        varchar about
    }
    jobs {
        bigint id PK
        bigint company_id FK
        bigint recruiter_id FK
        varchar title
        enum role_category
        varchar_array skills
        int experience_min
        int experience_max
        enum status "open | closed"
        tsvector search_vector "trigger, GIN"
        vector embedding "384-d, pgvector"
    }
    resumes {
        bigint id PK
        bigint user_id FK
        varchar storage_key "random, encrypted file"
        varchar status "processing | ready | failed"
        timestamptz consent_at
        varchar file_sha256
        varchar scan_result
        text raw_text
        jsonb parsed
        varchar_array skills "seeker-confirmed"
        vector embedding "of redacted text"
        bool is_current "partial unique index"
    }
    match_scores {
        bigint resume_id PK, FK
        bigint job_id PK, FK
        smallint score
        jsonb breakdown "components"
        varchar resume_hash "signature"
        varchar job_hash "signature"
    }
    applications {
        bigint id PK
        bigint job_id FK
        bigint seeker_id FK
        bigint resume_id FK "SET NULL"
        enum status
        unique job_seeker "job_id + seeker_id"
    }
    application_status_history {
        bigint id PK
        bigint application_id FK
        enum from_status
        enum to_status
        bigint changed_by FK
        timestamptz changed_at
    }
    interviews {
        bigint id PK
        bigint application_id FK
        timestamptz starts_at
        int duration_minutes
        varchar mode "video | phone | onsite"
        varchar status "scheduled | cancelled"
        int sequence "iCalendar SEQUENCE"
    }
    notifications {
        bigint id PK
        bigint user_id FK
        varchar type
        jsonb payload
        timestamptz read_at
        timestamptz emailed_at
    }
    saved_searches {
        bigint id PK
        bigint user_id FK
        jsonb params
        bool alerts_enabled
    }
    background_tasks {
        varchar id PK "Celery task id"
        varchar kind
        varchar status
        int attempts
        jsonb args
        jsonb result "retried_as"
        text error
    }
    audit_logs {
        bigint id PK
        bigint actor_id FK "SET NULL"
        varchar actor_role
        varchar action
        varchar target_type
        bigint target_id
        varchar request_id
    }
    saved_jobs {
        bigint user_id PK, FK
        bigint job_id PK, FK
    }
```

Also: `eval_runs` (evaluation metrics for the landing page) and the `search_terms`
materialized view (job vocabulary with a trigram index, for typo correction).

## Sign-in, refresh rotation and theft detection

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (SPA)
    participant A as API /api/auth
    participant DB as PostgreSQL
    participant R as Redis
    B->>A: POST /login {email, password} + X-CSRF-Protection
    A->>R: rate limit check (email + IP)
    A->>DB: load user, bcrypt verify
    A->>DB: insert refresh_tokens (hashed, new family)
    A->>DB: audit_logs auth.login
    A-->>B: access token (15 min, kept in memory) + Set-Cookie hike_refresh (HttpOnly)
    Note over B: access token expires, or the page reloads
    B->>A: POST /refresh (cookie) + X-CSRF-Protection
    A->>DB: token row valid and not revoked?
    A->>DB: revoke old row, insert new row (same family)
    A-->>B: new access token + rotated cookie
    Note over B,A: An attacker replays the old cookie
    B->>A: POST /refresh (old, already rotated cookie)
    A->>DB: row already revoked: reuse detected
    A->>DB: revoke every token in the family
    A-->>B: 401, the legitimate session must sign in again
```

## Resume upload and processing

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as API
    participant S as Storage (disk / S3)
    participant DB as PostgreSQL
    participant Q as Redis (queue)
    participant W as Celery worker
    participant P as Sandbox subprocess
    B->>A: POST /api/resumes (file, consent=true)
    A->>A: size, extension, MIME and magic-byte checks
    A->>A: malware screen (heuristics, optional ClamAV)
    A->>S: save Fernet-encrypted file under a random key
    A->>DB: resumes row (status processing, consent, sha256, scan result)
    A->>DB: background_tasks row (queued)
    A->>Q: process_resume(resume_id)
    A-->>B: 202 Accepted {status: processing}
    loop every second
        B->>A: GET /api/resumes/{id}
    end
    Q->>W: process_resume
    W->>DB: lock resume row (FOR UPDATE SKIP LOCKED)
    W->>S: read + decrypt
    W->>P: python -I doc_extract.py (no secrets, time/memory limits)
    P-->>W: extracted text
    W->>W: parse skills, years, education, contacts
    W->>DB: resume ready, task succeeded
    B->>A: GET /api/resumes/{id} -> ready
    B->>A: PUT /api/resumes/{id} (confirmed skills, years)
    A->>Q: derive_resume -> W embeds the redacted text, classifies the role
```

A file the sandbox cannot read ends as `failed` with a reason (task `rejected`, no alert).
An infrastructure error is retried 3 times with backoff, then dead-lettered, flagged on the
resume, and reported to admins, who can retry it from the System page.

## Search

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as API /api/jobs
    participant R as Redis
    participant DB as PostgreSQL
    participant M as MiniLM (ONNX)
    B->>A: GET /api/jobs?q=pyhton developer&location=Pune
    A->>R: cached candidates for (query, filters, jobs version)?
    alt cache miss
        A->>DB: typo check: does "pyhton" match any open job? no
        A->>DB: closest vocabulary word (pg_trgm + levenshtein): "python"
        A->>A: synonyms: (python) & (developer | engineer)
        A->>R: cached query embedding? (else compute with MiniLM)
        A->>DB: one query: filters AND (full-text OR title substring OR cosine >= 0.45), ts_rank_cd, cosine
        A->>R: store candidates (60 s, invalidated by jobs version)
    end
    A->>A: rank: text (lexical + semantic) + match score + recency + category, heap top-k
    A->>DB: match scores for the page (cached in match_scores)
    A-->>B: page of jobs + corrected_query "python developer"
```

## Applying, notifications and email

```mermaid
sequenceDiagram
    autonumber
    participant S as Seeker
    participant A as API
    participant DB as PostgreSQL
    participant W as Worker
    participant M as Email (log or SMTP)
    S->>A: POST /api/applications {job_id}
    A->>DB: insert application (unique job + seeker) + history row
    A->>DB: insert notification for the recruiter
    A->>DB: COMMIT
    Note over A: after_commit hook queues deliver_email
    A-->>S: 201
    W->>DB: lock notification row, skip if emailed_at set or user opted out
    W->>M: send (Message-ID notification-{id}@hike)
    W->>DB: emailed_at = now
```

## Interview scheduling

```mermaid
sequenceDiagram
    autonumber
    participant R as Recruiter
    participant A as API
    participant DB as PostgreSQL
    participant W as Worker
    participant C as Candidate
    R->>A: POST /api/recruiter/applications/{id}/interviews
    A->>A: own job? application in Interview stage? time in the future?
    A->>DB: interviews row (sequence 0), notification, audit entry
    A-->>R: 201 + Google Calendar link
    W->>C: email with interview.ics (METHOD:REQUEST, UID interview-{id}@hike)
    R->>A: PATCH /api/recruiter/interviews/{id} (new time)
    A->>DB: sequence 1, notification
    W->>C: updated .ics: calendar apps update the same event
    C->>A: GET /api/interviews/{id}/ics (download)
```

## Request path inside the API

```mermaid
flowchart LR
    In[Request] --> O[ObservabilityMiddleware<br/>request id, metrics, access log,<br/>security headers, JSON 500]
    O --> L{ConcurrencyLimit<br/>slot free within 10 s?}
    L -- no --> E503[503 Retry-After]
    L -- yes --> C[CORS]
    C --> D[Dependencies<br/>session, auth, role, CSRF]
    D --> H[Endpoint]
    H --> Sv[Services] --> DB[(PostgreSQL)]
    Sv --> Rd[(Redis)]
    Sv --> Q[[enqueue task]]
```
