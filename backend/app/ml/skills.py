"""Skill extraction: taxonomy lookup with greedy longest-match n-grams.

Text and aliases go through the same tokenizer, so "CI/CD" in a resume and the alias
"ci/cd" both become "ci cd". At each token we try the longest n-gram first (4 down to 1),
so "React Native" wins over "React" and "Spring Boot" over "Spring".

Case-sensitive entries (e.g. "Go", "Swift", "Spring") only match their exact single-word
canonical form, so the English words "go" or "spring" are not counted as skills.

Complexity: O(T * N) dictionary lookups for T tokens and max n-gram size N=4.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).parent / "data" / "skills_taxonomy.json"
MAX_NGRAM = 4

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#]*(?:\.[A-Za-z0-9+#]+)*")
_DOTNET_RE = re.compile(r"(?<![A-Za-z0-9])\.net\b", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    text = _DOTNET_RE.sub("dotnet", text)
    return _TOKEN_RE.findall(text)


@dataclass(frozen=True)
class Skill:
    name: str
    category: str


class SkillTaxonomy:
    def __init__(self, entries: list[dict]):
        self.skills: dict[str, Skill] = {}
        self._ci: dict[str, str] = {}  # lowercased token key -> canonical name
        self._cs: dict[str, str] = {}  # exact-case token key -> canonical name
        for e in entries:
            name = e["name"]
            self.skills[name.lower()] = Skill(name, e["category"])
            forms = [name, *e.get("aliases", [])]
            for form in forms:
                tokens = tokenize(form)
                if not tokens:
                    continue
                if e.get("case_sensitive") and form == name and len(tokens) == 1:
                    self._cs[tokens[0]] = name
                else:
                    self._ci.setdefault(" ".join(tokens).lower(), name)

    def __len__(self) -> int:
        return len(self.skills)

    def canonical(self, term: str) -> str | None:
        """Canonical name for a skill or alias typed by a user, or None if unknown."""
        tokens = tokenize(term)
        if not tokens:
            return None
        key = " ".join(tokens)
        return self._ci.get(key.lower()) or self._cs.get(key) or self._cs_fallback(key)

    def _cs_fallback(self, key: str) -> str | None:
        # A user typing "go" in the skill editor clearly means the language.
        for form, name in self._cs.items():
            if form.lower() == key.lower():
                return name
        return None

    def normalise(self, terms: list[str]) -> list[str]:
        """Map user-entered skills to canonical names, keeping unknown ones as typed."""
        seen, out = set(), []
        for t in terms:
            t = " ".join(t.split())
            name = self.canonical(t) or t
            if name and name.lower() not in seen:
                seen.add(name.lower())
                out.append(name)
        return out

    def extract(self, text: str) -> list[str]:
        """Skills mentioned in free text, in order of first appearance."""
        tokens = tokenize(text)
        lowered = [t.lower() for t in tokens]
        found: dict[str, None] = {}
        i = 0
        while i < len(tokens):
            matched = 0
            for n in range(min(MAX_NGRAM, len(tokens) - i), 0, -1):
                key_lower = " ".join(lowered[i : i + n])
                name = self._ci.get(key_lower)
                if name is None and n == 1:
                    name = self._cs.get(tokens[i])
                if name:
                    found.setdefault(name, None)
                    matched = n
                    break
            i += matched or 1
        return list(found)

    def category_of(self, name: str) -> str | None:
        s = self.skills.get(name.lower())
        return s.category if s else None

    def search(self, prefix: str, limit: int = 10) -> list[str]:
        p = prefix.lower().strip()
        if not p:
            return []
        names = [s.name for s in self.skills.values()]
        starts = [n for n in names if n.lower().startswith(p)]
        contains = [n for n in names if p in n.lower() and n not in starts]
        return (sorted(starts, key=len) + sorted(contains, key=len))[:limit]


@lru_cache
def get_taxonomy() -> SkillTaxonomy:
    data = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    return SkillTaxonomy(data["skills"])
