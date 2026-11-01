"""Prefix tree for title / skill autocomplete.

Every term is indexed under each of its word starts, so "Senior Backend Engineer" is found
by "sen", "back" and "eng". Each terminal node keeps {display_text: weight}; weight is how
many open jobs use the term, so common terms are suggested first.

insert: O(L) per indexed suffix (L = term length).
suggest: O(P) to walk the prefix + O(M log k) to pick the best k of the M terms below it.
"""

import heapq


class _Node:
    __slots__ = ("children", "terms")

    def __init__(self) -> None:
        self.children: dict[str, _Node] = {}
        self.terms: dict[str, int] = {}


class Trie:
    def __init__(self) -> None:
        self.root = _Node()
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def insert(self, term: str, weight: int = 1) -> None:
        term = " ".join(term.split())
        if not term:
            return
        words = term.lower().split(" ")
        for i in range(len(words)):
            self._insert_key(" ".join(words[i:]), term, weight)
        self._size += 1

    def _insert_key(self, key: str, display: str, weight: int) -> None:
        node = self.root
        for ch in key:
            node = node.children.setdefault(ch, _Node())
        node.terms[display] = node.terms.get(display, 0) + weight

    def _find(self, prefix: str) -> _Node | None:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def suggest(self, prefix: str, limit: int = 8) -> list[str]:
        prefix = " ".join(prefix.lower().split())
        if not prefix:
            return []
        start = self._find(prefix)
        if start is None:
            return []
        totals: dict[str, int] = {}
        stack = [start]
        while stack:  # iterative DFS: no recursion limit on long keys
            node = stack.pop()
            for display, w in node.terms.items():
                # A term can sit under several suffixes of the same subtree; keep the max.
                totals[display] = max(totals.get(display, 0), w)
            stack.extend(node.children.values())
        best = heapq.nsmallest(limit, totals.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        return [display for display, _ in best]

    def __contains__(self, term: str) -> bool:
        node = self._find(" ".join(term.lower().split()))
        return node is not None and any(d.lower() == term.lower().strip() for d in node.terms)
