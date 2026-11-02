"""Search relevance evaluation: NDCG@10 for each search feature, on the 50 seed jobs.

    python -m app.ml.eval_search             # needs the seeded database (docker compose up)
    python -m app.ml.eval_search --report    # also regenerate docs/search-evaluation.md

37 labelled queries (backend/eval/search/queries.json) in four groups: exact terms, typos,
synonyms/abbreviations, and natural-language descriptions. Each query runs through the real
search service (anonymous user, sort by relevance, first page of 10) under several
configurations, from the original lexical search to the full hybrid. Metrics per query,
averaged: NDCG@10 (graded gains 2^g - 1), Recall@10, MRR, and the zero-result rate, with 95%
bootstrap intervals and a paired comparison against the original search.

The semantic weight and threshold were chosen on these same queries (the sweep is in the
report), so the hybrid's score here is optimistic; the queries are a small, author-written
set, and the report says so.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.eval_holdout import bootstrap_ci, ndcg_at_k
from app.models import Job

BACKEND_DIR = Path(__file__).resolve().parents[2]
QUERIES_PATH = BACKEND_DIR / "eval" / "search" / "queries.json"
JOBS_PATH = BACKEND_DIR / "seed" / "data" / "jobs.json"
RESULTS_PATH = Path(__file__).parent / "eval_search_results.json"
REPORT_PATH = BACKEND_DIR.parent / "docs" / "search-evaluation.md"
K = 10


@dataclass(frozen=True)
class Config:
    name: str
    synonyms: bool
    typo: bool
    semantic_weight: float
    semantic_min: float = 0.45


BASELINE = Config("Lexical (before)", False, False, 0.0)
CONFIGS = [
    BASELINE,
    Config("+ synonyms", True, False, 0.0),
    Config("+ typo correction", False, True, 0.0),
    Config("+ synonyms + typos", True, True, 0.0),
    Config("Hybrid (production)", True, True, 0.4, 0.45),
]
SWEEP = [
    Config(f"w={w} min={m}", True, True, w, m) for w in (0.2, 0.4, 0.6) for m in (0.40, 0.45, 0.50)
]


def load() -> tuple[list[dict], dict[str, str]]:
    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))["queries"]
    titles = {str(j["key"]): j["title"] for j in json.loads(JOBS_PATH.read_text(encoding="utf-8"))}
    return queries, titles


def job_ids_by_key(db: Session, titles: dict[str, str]) -> dict[str, int]:
    """Seed job key -> database id (titles are unique in the seed data)."""
    rows = dict(db.execute(select(Job.title, Job.id)).all())
    missing = [t for t in titles.values() if t not in rows]
    if missing:
        raise SystemExit(f"database is not seeded with the seed jobs (missing {missing[:3]})")
    return {key: rows[title] for key, title in titles.items()}


def run_query(db: Session, q: str, cfg: Config) -> list[int]:
    from app.services.search import SearchParams, search_jobs

    params = SearchParams(
        q=q,
        page_size=K,
        synonyms=cfg.synonyms,
        typo=cfg.typo,
        semantic_weight=cfg.semantic_weight,
        semantic_min=cfg.semantic_min,
    )
    return search_jobs(db, params).job_ids


def per_query(ranked: list[int], grades: dict[int, int]) -> dict:
    relevant = {j for j, g in grades.items() if g >= 1}
    top = ranked[:K]
    first = next((i for i, j in enumerate(ranked, 1) if j in relevant), None)
    return {
        "ndcg_at_10": ndcg_at_k(ranked, grades, K),
        "recall_at_10": len(relevant & set(top)) / len(relevant),
        "mrr": 1 / first if first else 0.0,
        "zero_results": float(not ranked),
    }


def evaluate(db: Session, cfg: Config, queries: list[dict], ids: dict[str, int]) -> list[dict]:
    rows = []
    for item in queries:
        grades = {ids[k]: g for k, g in item["labels"].items()}
        ranked = run_query(db, item["q"], cfg)
        rows.append({"q": item["q"], "type": item["type"], **per_query(ranked, grades)})
    return rows


def summarise(rows: list[dict]) -> dict:
    out = {}
    for metric in ("ndcg_at_10", "recall_at_10", "mrr", "zero_results"):
        values = [r[metric] for r in rows]
        out[metric] = {"mean": round(float(np.mean(values)), 3), "ci95": bootstrap_ci(values)}
    out["by_type"] = {
        t: round(float(np.mean([r["ndcg_at_10"] for r in rows if r["type"] == t])), 3)
        for t in ("exact", "typo", "synonym", "natural")
    }
    return out


def run(db: Session) -> dict:
    from app.services.search import SearchParams  # noqa: F401  (fails early if app is broken)

    queries, titles = load()
    ids = job_ids_by_key(db, titles)
    per_config = {cfg.name: evaluate(db, cfg, queries, ids) for cfg in CONFIGS}
    base, full = per_config[BASELINE.name], per_config["Hybrid (production)"]
    diffs = [f["ndcg_at_10"] - b["ndcg_at_10"] for f, b in zip(full, base, strict=True)]
    sweep = {
        cfg.name: round(
            float(np.mean([r["ndcg_at_10"] for r in evaluate(db, cfg, queries, ids)])), 3
        )
        for cfg in SWEEP
    }
    return {
        "queries": len(queries),
        "jobs": len(ids),
        "k": K,
        "configs": {name: summarise(rows) for name, rows in per_config.items()},
        "hybrid_minus_lexical_ndcg": {
            "mean": round(float(np.mean(diffs)), 3),
            "ci95": bootstrap_ci(diffs, seed=13),
        },
        "semantic_sweep_ndcg": sweep,
        "per_query": {
            name: [
                {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}
                for r in rows
            ]
            for name, rows in per_config.items()
        },
    }


def semantic_note(m: dict) -> str:
    c = m["configs"]
    lexical_best = c["+ synonyms + typos"]["ndcg_at_10"]["mean"]
    hybrid = c["Hybrid (production)"]["ndcg_at_10"]["mean"]
    nat_before = c["+ synonyms + typos"]["by_type"]["natural"]
    nat_after = c["Hybrid (production)"]["by_type"]["natural"]
    return (
        f"Almost all of the gain comes from synonyms and typo correction. Adding the semantic "
        f"signal on top changes NDCG@10 by {hybrid - lexical_best:+.3f} overall and by "
        f"{nat_after - nat_before:+.3f} on natural-language queries: on job titles this "
        f"short and keyword-heavy, the embedding adds little. It stays on because it also "
        f"returns jobs that share no words with the query, but it is not where the improvement "
        f"comes from."
    )


def render(m: dict) -> str:
    lines = [
        "# Search relevance evaluation",
        "",
        "_Generated by `python -m app.ml.eval_search --report` from "
        "`backend/app/ml/eval_search_results.json`. Do not edit by hand._",
        "",
        f"{m['queries']} labelled queries against the {m['jobs']} seed jobs, run through the "
        f"real search service (anonymous, sort by relevance, top {m['k']}). Labels are graded "
        "(2 = what the searcher wants, 1 = acceptable further down); queries and labels were "
        "written with AI assistance and are not independently reviewed.",
        "",
        "| Configuration | NDCG@10 | Recall@10 | MRR | Zero results | Exact | Typo | Synonym | Natural |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, s in m["configs"].items():
        bt = s["by_type"]
        lines.append(
            f"| {name} | {s['ndcg_at_10']['mean']:.3f} ({s['ndcg_at_10']['ci95'][0]:.2f}-"
            f"{s['ndcg_at_10']['ci95'][1]:.2f}) | {s['recall_at_10']['mean']:.3f} | "
            f"{s['mrr']['mean']:.3f} | {s['zero_results']['mean'] * 100:.0f}% | "
            f"{bt['exact']:.3f} | {bt['typo']:.3f} | {bt['synonym']:.3f} | {bt['natural']:.3f} |"
        )
    d = m["hybrid_minus_lexical_ndcg"]
    verdict = (
        "a clear improvement on this set"
        if d["ci95"][0] > 0
        else "not a clear difference on this set"
    )
    lines += [
        "",
        f"Hybrid (production) minus the original lexical search, NDCG@10 per query: "
        f"{d['mean']:+.3f} (95% CI {d['ci95'][0]:+.3f} to {d['ci95'][1]:+.3f}): {verdict}.",
        "",
        "## What each feature does",
        "",
        "- **Typo correction** (`services/query_understanding.py`): a word that matches no open "
        "job is replaced by the closest title/skill word (PostgreSQL `pg_trgm` similarity and "
        "`fuzzystrmatch` edit distance, same first letter, at most 1-2 edits). The UI says "
        '"Showing results for ...".',
        '- **Synonyms** (`app/ml/data/search_synonyms.json`): "js" also matches JavaScript, '
        '"k8s" Kubernetes, "sde" software engineer, and so on.',
        "- **Hybrid ranking**: text relevance = (1 - w) x lexical + w x semantic, where "
        "semantic is the MiniLM cosine between the query and the job (rescaled). Jobs that "
        "share no words with the query are still candidates when the cosine is at least the "
        "threshold.",
        "",
        "## Choosing the semantic weight and threshold",
        "",
        "NDCG@10 of the full system for each setting (the production setting is w=0.4, "
        "min=0.45). Chosen on the same queries it is scored on, so the hybrid's number above is "
        "optimistic.",
        "",
        "| Setting | NDCG@10 |",
        "|---|---|",
        *[f"| {k} | {v:.3f} |" for k, v in m["semantic_sweep_ndcg"].items()],
        "",
        "## Limitations",
        "",
        f"- {m['queries']} queries over {m['jobs']} jobs is small; group means have 8-11 queries each.",
        "- Queries and labels were written by the project author with AI assistance.",
        "- Recency is part of the production ranking and depends on when the data was seeded.",
        "",
        "Reproduce: `docker compose up -d`, then `cd backend; python -m app.ml.eval_search --report`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    from app.db.session import SessionLocal

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    with SessionLocal() as db:
        m = run(db)
    RESULTS_PATH.write_text(json.dumps(m, indent=1), encoding="utf-8")
    for name, s in m["configs"].items():
        print(f"{name:<24} NDCG@10 {s['ndcg_at_10']['mean']:.3f}  by type {s['by_type']}")
    print("hybrid - lexical:", m["hybrid_minus_lexical_ndcg"])
    print("sweep:", m["semantic_sweep_ndcg"])
    if args.report:
        REPORT_PATH.write_text(render(m), encoding="utf-8")
        print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
