"""Job ranking for the seeker search ("sort by relevance").

    score = W_TEXT * text_relevance + W_MATCH * match + W_RECENCY * recency + W_CATEGORY * category_fit

- text_relevance: hybrid of lexical and semantic relevance (hybrid_text):
  lexical = Postgres ts_rank_cd (unbounded, >= 0) squashed into [0, 1) with r / (r + 1);
  semantic = MiniLM query/job cosine rescaled to [0, 1].
- match: the resume/job match score (0-100) / 100. Missing when the seeker has no resume.
- recency: exponential decay, exp(-ln2 * age_days / HALF_LIFE_DAYS): 1.0 today, 0.5 after 14 days.
- category_fit: 1 if the job's role category equals the category predicted for the resume.

When a signal is unavailable (no search text, no resume) its weight is removed and the
remaining weights are re-normalised so scores stay comparable within one result set.

Complexity for n candidate jobs and a requested page p of size s:
scoring is O(n), selecting the top k = p*s with a heap is O(n log k), so a page costs
O(n log k) instead of O(n log n) for a full sort.
"""

import heapq
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

W_TEXT = 0.45
W_MATCH = 0.35
W_RECENCY = 0.15
W_CATEGORY = 0.05
HALF_LIFE_DAYS = 14.0

T = TypeVar("T")


def recency_decay(posted_at: datetime, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    age_days = max((now - posted_at).total_seconds() / 86400.0, 0.0)
    return math.exp(-math.log(2) * age_days / HALF_LIFE_DAYS)


def normalise_text_rank(rank: float) -> float:
    rank = max(rank, 0.0)
    return rank / (rank + 1.0)


# MiniLM cosine between a short query and a whole job posting sits roughly in [0.1, 0.7];
# rescale to [0, 1] the same way the match score does.
SEM_FLOOR = 0.15
SEM_CEIL = 0.65


def semantic_scaled(cosine: float) -> float:
    return min(1.0, max(0.0, (cosine - SEM_FLOOR) / (SEM_CEIL - SEM_FLOOR)))


def hybrid_text(text_rank: float, cosine: float | None, semantic_weight: float) -> float:
    """Text relevance = (1 - w) * lexical + w * semantic. With w = 0 (or no embedding) it is
    the lexical score alone, as before the hybrid ranking existed."""
    lexical = normalise_text_rank(text_rank)
    if cosine is None or semantic_weight <= 0:
        return lexical
    return (1 - semantic_weight) * lexical + semantic_weight * semantic_scaled(cosine)


@dataclass(frozen=True)
class Signals:
    text: float | None  # [0,1) or None when there is no query
    match: float | None  # [0,1] or None when the seeker has no resume
    recency: float  # (0,1]
    category: float | None  # 0/1 or None when the resume category is unknown


def rank_score(s: Signals) -> float:
    parts = [
        (W_TEXT, s.text),
        (W_MATCH, s.match),
        (W_RECENCY, s.recency),
        (W_CATEGORY, s.category),
    ]
    available = [(w, v) for w, v in parts if v is not None]
    total_w = sum(w for w, _ in available)
    return sum(w * v for w, v in available) / total_w


def top_k(items: Iterable[T], key: Callable[[T], float], k: int) -> list[T]:
    """Highest-scoring k items, best first. O(n log k)."""
    return heapq.nlargest(k, items, key=key)
