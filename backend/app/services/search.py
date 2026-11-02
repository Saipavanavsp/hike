"""Seeker job search: Postgres full-text search + filters, cached in Redis, ranked in Python."""

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


@dataclass
class SearchResult:
    job_ids: list[int]
    total: int
    page: int
    page_size: int
    match_scores: dict[int, int]

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


def fetch_candidates(db: Session, p: SearchParams) -> list[Candidate]:
    key = p.cache_key()
    cached = cache.get_json(key)
    if cached is not None:
        return [Candidate(c[0], c[1], datetime.fromisoformat(c[2]), c[3], c[4]) for c in cached]

    q = p.q.strip()
    conds = _filters(p)
    if q:
        tsq = func.websearch_to_tsquery("english", q)
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        title_hit = Job.title.ilike(f"%{escaped}%", escape="\\")
        # FTS match, or a substring match on the title so partial words ("reac") still work.
        conds.append(or_(Job.search_vector.op("@@")(tsq), title_hit))
        rank = func.ts_rank_cd(Job.search_vector, tsq, 32) + case((title_hit, 0.1), else_=0.0)
    else:
        rank = cast(literal(0.0), Float)

    stmt = (
        select(Job.id, rank.label("rank"), Job.posted_at, Job.salary_max, Job.role_category)
        .where(*conds)
        .order_by(rank.desc(), Job.posted_at.desc())
        .limit(MAX_CANDIDATES)
    )
    rows = db.execute(stmt).all()
    candidates = [
        Candidate(r.id, float(r.rank or 0.0), r.posted_at, r.salary_max, r.role_category.value)
        for r in rows
    ]
    cache.set_json(
        key,
        [
            [c.job_id, c.text_rank, c.posted_at.isoformat(), c.salary_max, c.role_category]
            for c in candidates
        ],
        settings.search_cache_ttl_seconds,
    )
    return candidates


def job_matches(db: Session, p: SearchParams, job_id: int) -> bool:
    """Would this job appear in the results for these search params? (saved-search alerts)"""
    conds = [*_filters(p), Job.id == job_id]
    q = p.q.strip()
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        tsq = func.websearch_to_tsquery("english", q)
        conds.append(
            or_(Job.search_vector.op("@@")(tsq), Job.title.ilike(f"%{escaped}%", escape="\\"))
        )
    return db.scalar(select(Job.id).where(*conds)) is not None


MatchLookup = Callable[[list[int]], dict[int, int]]


def search_jobs(
    db: Session,
    p: SearchParams,
    match_lookup: MatchLookup | None = None,
    resume_category: str | None = None,
) -> SearchResult:
    candidates = fetch_candidates(db, p)
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
                    text=ranking.normalise_text_rank(c.text_rank) if has_query else None,
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
    )
