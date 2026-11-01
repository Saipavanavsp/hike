"""In-memory autocomplete index, rebuilt lazily whenever the jobs version in Redis changes.

Each API worker keeps its own Trie; comparing against the shared Redis counter means a job
created through any worker invalidates every worker's index on its next request.
"""

import threading
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job
from app.models.enums import JobStatus
from app.services.cache import jobs_version
from app.services.trie import Trie


class AutocompleteIndex:
    def __init__(self) -> None:
        self.titles = Trie()
        self.skills = Trie()
        self.version: int | None = None
        self._lock = threading.Lock()

    def build(self, db: Session) -> None:
        rows = db.execute(select(Job.title, Job.skills).where(Job.status == JobStatus.open)).all()
        title_counts = Counter(t for t, _ in rows)
        skill_counts = Counter(s for _, skills in rows for s in skills)
        titles, skills = Trie(), Trie()
        for term, n in title_counts.items():
            titles.insert(term, n)
        for term, n in skill_counts.items():
            skills.insert(term, n)
        self.titles, self.skills = titles, skills

    def ensure_fresh(self, db: Session) -> None:
        current = jobs_version()
        # -1 means Redis is unreachable: rebuild every time rather than serve stale data.
        if self.version == current and current != -1:
            return
        with self._lock:
            if self.version != current or current == -1:
                self.build(db)
                self.version = current

    def suggest(self, db: Session, prefix: str, limit: int = 8) -> list[dict]:
        self.ensure_fresh(db)
        titles = self.titles.suggest(prefix, limit)
        skills = self.skills.suggest(prefix, limit)
        # Interleave so both kinds show up, titles first.
        out: list[dict] = []
        for i in range(limit):
            if i < len(titles):
                out.append({"text": titles[i], "kind": "title"})
            if i < len(skills):
                out.append({"text": skills[i], "kind": "skill"})
        return out[:limit]


index = AutocompleteIndex()
