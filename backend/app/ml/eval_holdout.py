"""Holdout evaluation: matching quality on hand-written resumes and jobs, kept separate from
the seed data the system was tuned on.

    python -m app.ml.eval_holdout             # print, write app/ml/eval_holdout_results.json
    python -m app.ml.eval_holdout --report    # also regenerate docs/evaluation.md
    python -m app.ml.eval_holdout --export-labels labels.csv   # every pair, for human review
    python -m app.ml.eval_holdout --import-labels labels.csv   # write reviewed labels back

Data (backend/eval/holdout): 24 resumes rendered as PDF/DOCX in four layouts, 34 jobs
including 6 non-software distractors, graded labels (2 strong, 1 partial, 0 not a fit).
Every resume goes through the production parser, so parsing errors count against matching.

Methods: TF-IDF cosine (lexical baseline), MiniLM cosine (embeddings only), and the Hike
hybrid score used in production (semantic + skills + experience + location).
Metrics per resume, averaged, with 95% bootstrap intervals over resumes:
  P@5, R@5 and MRR (relevant = grade >= 1), and NDCG@5 with graded gains (2^g - 1).
Also: results per role category and per document layout, parser accuracy per layout, and
format invariance (the same resume in four layouts: how much do its scores move?).
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

from app.ml.embeddings import embed_documents
from app.ml.skills import get_taxonomy
from app.ml.tfidf import TfidfMatcher
from app.services.doc_extract import extract_text
from app.services.resume_parser import MONTHS, parse_resume

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "eval" / "holdout"
RESULTS_PATH = Path(__file__).parent / "eval_holdout_results.json"
REPORT_PATH = BACKEND_DIR.parent / "docs" / "evaluation.md"
TODAY = date(2026, 11, 1)  # fixed, so "Present" resolves the same way on every run
K = 5
BOOTSTRAP = 2000
METHODS = ("tfidf", "minilm", "hike")
EXT = {"pdf_classic": "pdf", "pdf_two_column": "pdf", "docx_table": "docx", "docx_caps": "docx"}


# ---------- data ----------


def load() -> tuple[list[dict], list[dict], dict[str, dict[str, int]]]:
    jobs = json.loads((DATA_DIR / "jobs.json").read_text(encoding="utf-8"))
    resumes = json.loads((DATA_DIR / "resumes.json").read_text(encoding="utf-8"))
    labels = json.loads((DATA_DIR / "labels.json").read_text(encoding="utf-8"))["labels"]
    return jobs, resumes, labels


def gold_years(experience: list[dict], today: date = TODAY) -> float:
    """Total experience from the structured dates (inclusive months, overlaps merged)."""
    now = today.year * 12 + today.month - 1
    spans = []
    for e in experience:
        start, end = (s.strip() for s in e["dates"].split(" - "))
        m, y = start.split()
        s_idx = int(y) * 12 + MONTHS[m[:3].lower()] - 1
        if end.lower() == "present":
            e_idx = now
        else:
            m2, y2 = end.split()
            e_idx = int(y2) * 12 + MONTHS[m2[:3].lower()] - 1
        spans.append((s_idx, e_idx))
    spans.sort()
    total, (cs, ce) = 0, spans[0]
    for s, e in spans[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            total += ce - cs + 1
            cs, ce = s, e
    total += ce - cs + 1
    return round(total / 12, 1)


def parse_file(path: Path) -> tuple[str, object]:
    kind = path.suffix.lstrip(".")
    text = extract_text(path.read_bytes(), kind)
    return text, parse_resume(text, today=TODAY)


# ---------- metrics ----------


def ndcg_at_k(ranked: list[str], grades: dict[str, int], k: int = K) -> float:
    gains = [2 ** grades.get(key, 0) - 1 for key in ranked[:k]]
    dcg = sum(g / np.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted((2**g - 1 for g in grades.values()), reverse=True)[:k]
    idcg = sum(g / np.log2(i + 2) for i, g in enumerate(ideal))
    return float(dcg / idcg) if idcg else 0.0


def per_resume_metrics(ranked: list[str], grades: dict[str, int]) -> dict:
    relevant = {key for key, g in grades.items() if g >= 1}
    top = ranked[:K]
    hits = sum(1 for key in top if key in relevant)
    first = next((i for i, key in enumerate(ranked, 1) if key in relevant), None)
    return {
        "p_at_5": hits / K,
        "r_at_5": hits / len(relevant) if relevant else 0.0,
        "mrr": 1 / first if first else 0.0,
        "ndcg_at_5": ndcg_at_k(ranked, grades),
    }


def bootstrap_ci(values: list[float], n: int = BOOTSTRAP, seed: int = 7) -> list[float]:
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    means = arr[rng.integers(0, len(arr), size=(n, len(arr)))].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return [round(float(lo), 3), round(float(hi), 3)]


def paired_difference(a: list[dict], b: list[dict], metric: str, seed: int = 11) -> dict:
    """Mean of (a - b) per resume, with a paired bootstrap interval. Excludes 0 = no clear
    difference on this data."""
    diffs = [x[metric] - y[metric] for x, y in zip(a, b, strict=True)]
    return {"mean": round(float(np.mean(diffs)), 3), "ci95": bootstrap_ci(diffs, seed=seed)}


def summarise(rows: list[dict]) -> dict:
    out = {}
    for metric in ("p_at_5", "r_at_5", "mrr", "ndcg_at_5"):
        values = [r[metric] for r in rows]
        out[metric] = {"mean": round(float(np.mean(values)), 3), "ci95": bootstrap_ci(values)}
    return out


# ---------- scoring ----------


def hike_scores(parsed: list, res_vecs: np.ndarray, jobs: list[dict], job_vecs) -> np.ndarray:
    from app.services.matching import JobSide, ResumeSide, compute_match

    scores = np.zeros((len(parsed), len(jobs)))
    for i, p in enumerate(parsed):
        side = ResumeSide(
            vector=res_vecs[i],
            skills=p.skills,
            years=p.years_experience,
            locations={p.location.lower()} if p.location else set(),
            open_to_remote=True,
        )
        for j, job in enumerate(jobs):
            js = JobSide(
                vector=job_vecs[j],
                skills=job["skills"],
                experience_min=job["experience_min"],
                experience_max=job["experience_max"],
                location=job["location"],
                remote_type=job["remote_type"],
            )
            scores[i, j] = compute_match(side, js)["score"]
    return scores


def job_texts(jobs: list[dict]) -> list[str]:
    from app.services.matching import job_text

    return [job_text(j["title"], j["skills"], j["description_md"]) for j in jobs]


def rank(scores_row: np.ndarray, job_keys: list[str]) -> list[str]:
    return [job_keys[j] for j in np.argsort(-scores_row, kind="stable")]


# ---------- evaluation ----------


def parser_accuracy(resumes: list[dict], parsed: list) -> list[dict]:
    tax = get_taxonomy()
    rows = []
    for r, p in zip(resumes, parsed, strict=True):
        gold = {tax.canonical(s) for s in r["gold_skills"]}
        known = {g for g in gold if g}
        found = {tax.canonical(s) or s for s in p.skills}
        tp = len(known & found)
        rows.append(
            {
                "key": r["key"],
                "format": r["format"],
                "skill_recall": tp / len(known) if known else 1.0,
                "skill_precision": tp / len(found) if found else 1.0,
                "taxonomy_coverage": len(known) / len(r["gold_skills"]),
                "years_abs_error": (
                    abs(p.years_experience - gold_years(r["experience"]))
                    if p.years_experience is not None
                    else None
                ),
                "name_ok": p.name == r["name"],
                "email_ok": p.email == r["email"],
                "location_ok": p.location == r["location"],
            }
        )
    return rows


def _mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(float(np.mean(values)), 3) if values else None


def format_invariance(jobs: list[dict], job_vecs, job_keys) -> dict:
    """Same content in four layouts: spread of Hike scores and stability of the top 5."""
    variants = sorted((DATA_DIR / "variants").glob("*.*"))
    by_resume: dict[str, dict[str, Path]] = {}
    for path in variants:
        key, layout = path.stem.split("-", 1)
        by_resume.setdefault(key, {})[layout] = path
    spreads, overlaps, per_layout_years = [], [], {layout: [] for layout in EXT}
    resumes = {r["key"]: r for r in load()[1]}
    for key, layouts in sorted(by_resume.items()):
        names = sorted(layouts)
        parsed = [parse_file(layouts[n]) for n in names]
        vecs = embed_documents([t for t, _ in parsed])
        scores = hike_scores([p for _, p in parsed], vecs, jobs, job_vecs)
        spreads.append(float(np.mean(scores.max(axis=0) - scores.min(axis=0))))
        tops = [set(rank(row, job_keys)[:K]) for row in scores]
        overlaps.append(float(np.mean([len(tops[0] & t) / K for t in tops[1:]])))
        truth = gold_years(resumes[key]["experience"])
        for n, (_, p) in zip(names, parsed, strict=True):
            err = abs(p.years_experience - truth) if p.years_experience is not None else None
            per_layout_years[n].append(err)
    return {
        "resumes": len(by_resume),
        "mean_score_spread_points": round(float(np.mean(spreads)), 2),
        "max_score_spread_points": round(float(np.max(spreads)), 2),
        "top5_overlap_vs_first_layout": round(float(np.mean(overlaps)), 3),
        "years_abs_error_by_layout": {k: _mean(v) for k, v in per_layout_years.items()},
    }


def run() -> dict:
    jobs, resumes, labels = load()
    job_keys = [j["key"] for j in jobs]
    other_jobs = {j["key"] for j in jobs if j["category"] == "other"}
    texts, parsed = [], []
    for r in resumes:
        text, p = parse_file(DATA_DIR / "files" / f"{r['key']}.{EXT[r['format']]}")
        texts.append(text)
        parsed.append(p)

    jtexts = job_texts(jobs)
    tfidf = TfidfMatcher().fit(jtexts + texts).similarity(texts, jtexts)
    job_vecs = embed_documents(jtexts)
    res_vecs = embed_documents(texts)
    method_scores = {
        "tfidf": tfidf,
        "minilm": res_vecs @ job_vecs.T,
        "hike": hike_scores(parsed, res_vecs, jobs, job_vecs),
    }

    rows: dict[str, list[dict]] = {m: [] for m in METHODS}
    distractor_slots = {m: 0 for m in METHODS}
    for m, scores in method_scores.items():
        for i, r in enumerate(resumes):
            ranked = rank(scores[i], job_keys)
            row = per_resume_metrics(ranked, labels[r["key"]])
            row.update(key=r["key"], category=r["category"], format=r["format"])
            rows[m].append(row)
            if r["category"] != "other":
                distractor_slots[m] += sum(1 for k in ranked[:K] if k in other_jobs)

    def group(field: str) -> dict:
        values = sorted({r[field] for r in rows["hike"]})
        return {
            v: {
                "n": sum(1 for r in rows["hike"] if r[field] == v),
                **{
                    m: {
                        "p_at_5": _mean(r["p_at_5"] for r in rows[m] if r[field] == v),
                        "ndcg_at_5": _mean(r["ndcg_at_5"] for r in rows[m] if r[field] == v),
                    }
                    for m in METHODS
                },
            }
            for v in values
        }

    acc = parser_accuracy(resumes, parsed)
    parser_by_format = {
        fmt: {
            "skill_recall": _mean(a["skill_recall"] for a in acc if a["format"] == fmt),
            "skill_precision": _mean(a["skill_precision"] for a in acc if a["format"] == fmt),
            "years_abs_error": _mean(a["years_abs_error"] for a in acc if a["format"] == fmt),
            "name_ok": _mean(a["name_ok"] for a in acc if a["format"] == fmt),
            "email_ok": _mean(a["email_ok"] for a in acc if a["format"] == fmt),
            "location_ok": _mean(a["location_ok"] for a in acc if a["format"] == fmt),
        }
        for fmt in EXT
    }
    grades = [g for per in labels.values() for g in per.values()]
    n_software = sum(1 for r in resumes if r["category"] != "other")
    # Best possible P@5: most resumes have fewer than 5 acceptable jobs.
    oracle_p5 = np.mean([min(len(labels[r["key"]]), K) / K for r in resumes])
    return {
        "dataset": {
            "resumes": len(resumes),
            "jobs": len(jobs),
            "distractor_jobs": len(other_jobs),
            "strong_pairs": grades.count(2),
            "partial_pairs": grades.count(1),
            "pairs": len(resumes) * len(jobs),
            "oracle_p_at_5": round(float(oracle_p5), 3),
            "today": TODAY.isoformat(),
        },
        "methods": {m: summarise(rows[m]) for m in METHODS},
        "paired_differences": {
            f"hike_minus_{other}": {
                metric: paired_difference(rows["hike"], rows[other], metric)
                for metric in ("p_at_5", "ndcg_at_5")
            }
            for other in ("tfidf", "minilm")
        },
        "distractors_in_top5": {
            m: round(distractor_slots[m] / (n_software * K), 3) for m in METHODS
        },
        "by_category": group("category"),
        "by_format": group("format"),
        "parser_by_format": parser_by_format,
        "taxonomy_coverage": _mean(a["taxonomy_coverage"] for a in acc),
        "format_invariance": format_invariance(jobs, job_vecs, job_keys),
        "per_resume": {
            m: [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in rs]
            for m, rs in rows.items()
        },
    }


# ---------- labels review ----------


def export_labels(path: Path) -> None:
    jobs, resumes, labels = load()
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["resume", "resume_summary", "job", "job_title", "grade"])
        for r in resumes:
            for j in jobs:
                w.writerow(
                    [
                        r["key"],
                        r["summary"],
                        j["key"],
                        j["title"],
                        labels[r["key"]].get(j["key"], 0),
                    ]
                )


def import_labels(path: Path) -> None:
    doc = json.loads((DATA_DIR / "labels.json").read_text(encoding="utf-8"))
    new: dict[str, dict[str, int]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            g = int(row["grade"])
            if g not in (0, 1, 2):
                raise ValueError(f"grade must be 0, 1 or 2: {row}")
            if g:
                new.setdefault(row["resume"], {})[row["job"]] = g
    doc["labels"] = new
    doc["provenance"] += " Reviewed labels imported from CSV."
    (DATA_DIR / "labels.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


# ---------- output ----------


def print_report(m: dict) -> None:
    d = m["dataset"]
    print(
        f"\nHoldout: {d['resumes']} resumes x {d['jobs']} jobs "
        f"({d['strong_pairs']} strong + {d['partial_pairs']} partial pairs)"
    )
    print(f"{'method':<8}{'P@5':>14}{'R@5':>14}{'MRR':>14}{'NDCG@5':>14}")
    for name, r in m["methods"].items():
        cells = [f"{r[k]['mean']:.3f}" for k in ("p_at_5", "r_at_5", "mrr", "ndcg_at_5")]
        print(f"{name:<8}" + "".join(f"{c:>14}" for c in cells))
    print("distractor share of top-5:", m["distractors_in_top5"])
    print("format invariance:", m["format_invariance"])


def write_report(m: dict, path: Path = REPORT_PATH) -> None:
    from app.ml.eval_report import render

    path.write_text(render(m), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true", help="regenerate docs/evaluation.md")
    ap.add_argument("--export-labels", type=Path)
    ap.add_argument("--import-labels", type=Path)
    args = ap.parse_args(argv)
    if args.export_labels:
        export_labels(args.export_labels)
        print(f"wrote {args.export_labels}")
        return
    if args.import_labels:
        import_labels(args.import_labels)
        print("labels.json updated")
    metrics = run()
    RESULTS_PATH.write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    print_report(metrics)
    if args.report:
        write_report(metrics)
        print(f"\nwrote {REPORT_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
