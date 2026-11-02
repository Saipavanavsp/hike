"""Turn a search box query into a PostgreSQL full-text query: typo correction + synonyms.

1. Typo correction. A query word that matches no open job at all (checked against the
   full-text index, so description words count) is replaced by the closest word from the
   job vocabulary (titles and skills, the search_terms view): same first letter, edit
   distance <= 1 for short words and <= 2 for longer ones, ties broken by trigram
   similarity and how many jobs use the word. "pyhton developer" -> "python developer".
   The UI shows "Showing results for ...".
2. Synonyms. Words and phrases are matched greedily (longest first) against the groups in
   app/ml/data/search_synonyms.json, and each becomes an OR of its variants:
   "js developer" -> (javascript | js) & (developer | engineer).
Queries that use web-search syntax ("quoted phrase", -exclude, OR) are passed through
unchanged to websearch_to_tsquery.
"""

import contextlib
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache, reduce
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.services import cache

SYNONYMS_PATH = Path(__file__).resolve().parents[1] / "ml" / "data" / "search_synonyms.json"
WORD = re.compile(r"[a-z0-9][a-z0-9+#./-]*")
STOPWORDS = {"a", "an", "and", "the", "for", "with", "in", "of", "to", "at", "on", "job", "jobs"}
WEBSEARCH_SYNTAX = re.compile(r'"|(^|\s)-\w|\bor\b', re.IGNORECASE)
TERMS_VERSION_KEY = "hike:search_terms:version"


@dataclass
class Synonyms:
    groups: list[list[str]]
    index: dict[str, list[str]] = field(default_factory=dict)
    words: set[str] = field(default_factory=set)
    max_words: int = 1

    def __post_init__(self) -> None:
        for group in self.groups:
            for variant in group:
                self.index[variant] = group
                self.words.update(WORD.findall(variant))
                self.max_words = max(self.max_words, len(variant.split()))


@lru_cache
def synonyms() -> Synonyms:
    data = json.loads(SYNONYMS_PATH.read_text(encoding="utf-8"))
    return Synonyms(groups=data["groups"])


@dataclass
class QueryPlan:
    raw: str
    corrected: str | None  # set only when a word was corrected
    units: list[list[str]]  # AND of units, each an OR of variants
    websearch: bool = False

    @property
    def effective(self) -> str:
        return self.corrected or self.raw


def tokenize(q: str) -> list[str]:
    return WORD.findall(q.lower())


def refresh_terms(db: Session) -> None:
    """Refresh the vocabulary view once per jobs version (any job change bumps it)."""
    version = str(cache.jobs_version())
    try:
        current = get_redis().get(TERMS_VERSION_KEY)
    except Exception:
        current = None
    if isinstance(current, bytes):
        current = current.decode()
    if current == version:
        return
    db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY search_terms"))
    db.commit()
    with contextlib.suppress(Exception):
        get_redis().set(TERMS_VERSION_KEY, version)


def _matches_any_job(db: Session, word: str) -> bool:
    return bool(
        db.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM jobs WHERE status = 'open' "
                "AND search_vector @@ plainto_tsquery('english', :w))"
            ),
            {"w": word},
        )
    )


def _closest_term(db: Session, word: str) -> str | None:
    max_distance = 1 if len(word) <= 4 else 2
    row = db.execute(
        text("""
            SELECT term, levenshtein(term, :w) AS d
            FROM search_terms
            WHERE position(' ' in term) = 0
              AND left(term, 1) = left(:w, 1)
              AND abs(length(term) - length(:w)) <= :maxd
              AND (term % :w OR levenshtein(term, :w) <= :maxd)
            ORDER BY d, similarity(term, :w) DESC, jobs DESC, term
            LIMIT 1
            """),
        {"w": word, "maxd": max_distance},
    ).first()
    return row.term if row is not None and row.d <= max_distance else None


def correct(db: Session, tokens: list[str]) -> list[str]:
    syn = synonyms()
    refresh_terms(db)
    out = []
    for t in tokens:
        if (
            len(t) < 4
            or t in STOPWORDS
            or t in syn.words
            or not t.isalpha()
            or _matches_any_job(db, t)
        ):
            out.append(t)
            continue
        out.append(_closest_term(db, t) or t)
    return out


def plan(db: Session, q: str, use_synonyms: bool = True, use_typo: bool = True) -> QueryPlan:
    q = " ".join(q.split())
    if WEBSEARCH_SYNTAX.search(q):
        return QueryPlan(raw=q, corrected=None, units=[], websearch=True)
    tokens = tokenize(q)
    fixed = correct(db, tokens) if use_typo else tokens
    corrected = " ".join(fixed) if fixed != tokens else None
    syn = synonyms()
    units: list[list[str]] = []
    i = 0
    while i < len(fixed):
        for n in range(min(syn.max_words, len(fixed) - i), 0, -1):
            phrase = " ".join(fixed[i : i + n])
            if use_synonyms and phrase in syn.index:
                units.append(list(syn.index[phrase]))
                i += n
                break
            if n == 1:
                if phrase not in STOPWORDS:
                    units.append([phrase])
                i += 1
    return QueryPlan(raw=q, corrected=corrected, units=units)


def tsquery(p: QueryPlan):
    """SQL expression for the plan: AND of units, each an OR of phrase queries."""
    if p.websearch or not p.units:
        return func.websearch_to_tsquery("english", p.raw)
    ors = [
        reduce(lambda a, b: a.op("||")(b), [func.phraseto_tsquery("english", v) for v in unit])
        for unit in p.units
    ]
    return reduce(lambda a, b: a.op("&&")(b), ors)
