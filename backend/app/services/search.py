"""Seeker job search: Postgres full-text search with typo correction and synonyms, plus a
semantic (MiniLM) signal, filters, Redis cache, ranked in Python.

Candidates are jobs that pass the filters and either match the full-text query (or the
title, as a substring) or are semantically close to it (cosine >= semantic_min), so a
query worded differently from the job text can still find it. See query_understanding.py
for the full-text side and docs/search-evaluation.md for how the settings were chosen.
"""

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Float, and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Job
from app.models.enums import JobStatus, RemoteType, RoleCategory
from app.services import cache, ranking

PAGE_SIZE = 20
MAX_CANDIDATES = 1000
SORTS = ("relevance", "newest", "salary", "match")


@dataclass
class SearchParams:
    q: str = ""
    locations: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    remote: list[str] = field(default_factory=list)
    experience: int | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    sort: str = "relevance"
    page: int = 1
    page_size: int = PAGE_SIZE
    # Search features (defaults from settings; the evaluation switches them individually).
    synonyms: bool = field(default_factory=lambda: settings.search_synonyms)
    typo: bool = field(default_factory=lambda: settings.search_typo)
    semantic_weight: float = field(default_factory=lambda: settings.search_semantic_weight)
    semantic_min: float = field(default_factory=lambda: settings.search_semantic_min)

    def cache_key(self) -> str:
        # Page and sort are applied after the cache, so they are not part of the key.
        d = asdict(self)
        for k in ("sort", "page", "page_size"):
            d.pop(k)
        d["q"] = " ".join(self.q.lower().split())
        for k in ("locations", "roles", "remote"):
            d[k] = sorted(v.lower() for v in d[k])
        digest = hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]
        return f"search:v{cache.jobs_version()}:{digest}"


@dataclass
class Candidate:
    job_id: int
    text_rank: float
    posted_at: datetime
    salary_max: int
    role_category: str
    semantic: float | None = None  # query/job cosine; None without a query or semantic off


@dataclass
class SearchResult:
    job_ids: list[int]
    total: int
    page: int
    page_size: int
    match_scores: dict[int, int]
    corrected_query: str | None = None

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.page_size))


def _filters(p: SearchParams) -> list:
    conds = [Job.status == JobStatus.open]
    if p.locations:
        wanted = [loc.lower() for loc in p.locations]
        loc_conds = [func.lower(Job.location).in_(wanted)]
        if "remote" in wanted:
            loc_conds.append(Job.remote_type == RemoteType.remote)
        conds.append(or_(*loc_conds))
    if p.roles:
        conds.append(Job.role_category.in_([RoleCategory(r) for r in p.roles]))
    if p.remote:
        conds.append(Job.remote_type.in_([RemoteType(r) for r in p.remote]))
    if p.experience is not None:
        conds.append(and_(Job.experience_min <= p.experience, Job.experience_max >= p.experience))
    # Salary filters use range overlap: the job's band must intersect the requested band.
    if p.salary_min is not None:
        conds.append(Job.salary_max >= p.salary_min)
    if p.salary_max is not None:
        conds.append(Job.salary_min <= p.salary_max)
    return conds


def query_vector(q: str) -> list[float]:
    """MiniLM embedding of the query, cached in Redis for a day (queries repeat a lot)."""
    from app.ml.embeddings import embed_documents

    key = "qvec:" + hashlib.sha1(q.lower().encode()).hexdigest()
    hit = cache.get_json(key)
    if hit is not None:
        return hit
    vec = [round(float(x), 6) for x in embed_documents([q])[0]]
    cache.set_json(key, vec, 86400)
    return vec


def fetch_candidates(db: Session, p: SearchParams) -> tuple[list[Candidate], str | None]:
    """Candidate jobs for the query and filters, and the corrected query (if any)."""
    from app.services.query_understanding import plan as make_plan
    from app.services.query_understanding import tsquery

    key = p.cache_key()
    cached = cache.get_json(key)
    if cached is not None:
        return [
            Candidate(c[0], c[1], datetime.fromisoformat(c[2]), c[3], c[4], c[5])
            for c in cached["c"]
        ], cached["corrected"]

    q = p.q.strip()
    conds = _filters(p)
    corrected = None
    semantic = None
    if q:
        qp = make_plan(db, q, use_synonyms=p.synonyms, use_typo=p.typo)
        corrected = qp.corrected
        tsq = tsquery(qp)
        title_q = qp.effective.lower()
        escaped = title_q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        # Substring match on the title (trigram index) so partial words ("reac") still work.
        title_hit = func.lower(Job.title).like(f"%{escaped}%", escape="\\")
        lexical = or_(Job.search_vector.op("@@")(tsq), title_hit)
        rank = func.ts_rank_cd(Job.search_vector, tsq, 32) + case((title_hit, 0.1), else_=0.0)
        rank = case((lexical, rank), else_=0.0)
        if p.semantic_weight > 0:
            qvec = query_vector(qp.effective)
            semantic = 1 - Job.embedding.cosine_distance(qvec)
            # Lexical matches, plus jobs that are close in meaning even with no shared words.
            conds.append(or_(lexical, semantic >= p.semantic_min))
        else:
            conds.append(lexical)
    else:
        rank = cast(literal(0.0), Float)

    sem_col = (
        func.coalesce(semantic, 0.0).label("sem")
        if semantic is not None
        else literal(None).label("sem")
    )
    stmt = (
        select(
            Job.id, rank.label("rank"), Job.posted_at, Job.salary_max, Job.role_category, sem_col
        )
        .where(*conds)
        .order_by(rank.desc(), Job.posted_at.desc())
        .limit(MAX_CANDIDATES)
    )
    rows = db.execute(stmt).all()
    candidates = [
        Candidate(
            r.id,
            float(r.rank or 0.0),
            r.posted_at,
            r.salary_max,
            r.role_category.value,
            float(r.sem) if r.sem is not None else None,
        )
        for r in rows
    ]
    cache.set_json(
        key,
        {
            "corrected": corrected,
            "c": [
                [
                    c.job_id,
                    c.text_rank,
                    c.posted_at.isoformat(),
                    c.salary_max,
                    c.role_category,
                    c.semantic,
                ]
                for c in candidates
            ],
        },
        settings.search_cache_ttl_seconds,
    )
    return candidates, corrected


def job_matches(db: Session, p: SearchParams, job_id: int) -> bool:
    """Would this job appear in the results for these search params? (saved-search alerts)"""
    from app.services.query_understanding import plan as make_plan
    from app.services.query_understanding import tsquery

    conds = [*_filters(p), Job.id == job_id]
    q = p.q.strip()
    if q:
        # Same full-text side as the search page (typos, synonyms); no semantic-only
        # matches, so alerts stay precise.
        qp = make_plan(db, q, use_synonyms=p.synonyms, use_typo=p.typo)
        escaped = qp.effective.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conds.append(
            or_(
                Job.search_vector.op("@@")(tsquery(qp)),
                func.lower(Job.title).like(f"%{escaped}%", escape="\\"),
            )
        )
    return db.scalar(select(Job.id).where(*conds)) is not None


MatchLookup = Callable[[list[int]], dict[int, int]]


def search_jobs(
    db: Session,
    p: SearchParams,
    match_lookup: MatchLookup | None = None,
    resume_category: str | None = None,
) -> SearchResult:
    candidates, corrected = fetch_candidates(db, p)
    total = len(candidates)
    k = p.page * p.page_size
    has_query = bool(p.q.strip())

    # Match scores are needed for every candidate when sorting by relevance or match.
    scores: dict[int, int] = {}
    if match_lookup and p.sort in ("relevance", "match"):
        scores = match_lookup([c.job_id for c in candidates])

    now = datetime.now(UTC)
    if p.sort == "newest":
        ordered = ranking.top_k(candidates, key=lambda c: c.posted_at.timestamp(), k=k)
    elif p.sort == "salary":
        ordered = ranking.top_k(candidates, key=lambda c: c.salary_max, k=k)
    elif p.sort == "match" and scores:
        ordered = ranking.top_k(
            candidates, key=lambda c: (scores.get(c.job_id, 0), c.posted_at.timestamp()), k=k
        )
    else:

        def score(c: Candidate) -> float:
            return ranking.rank_score(
                ranking.Signals(
                    text=(
                        ranking.hybrid_text(c.text_rank, c.semantic, p.semantic_weight)
                        if has_query
                        else None
                    ),
                    match=scores[c.job_id] / 100 if c.job_id in scores else None,
                    recency=ranking.recency_decay(c.posted_at, now),
                    category=(
                        float(c.role_category == resume_category) if resume_category else None
                    ),
                )
            )

        ordered = ranking.top_k(candidates, key=score, k=k)

    page_ids = [c.job_id for c in ordered[(p.page - 1) * p.page_size : k]]
    if match_lookup and not scores:
        scores = match_lookup(page_ids)
    return SearchResult(
        job_ids=page_ids,
        total=total,
        page=p.page,
        page_size=p.page_size,
        match_scores={jid: scores[jid] for jid in page_ids if jid in scores},
        corrected_query=corrected,
    )
