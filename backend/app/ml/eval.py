"""Evaluation harness for matching and the role classifier.

    python -m app.ml.eval            # print report, write app/ml/eval_results.json
    python -m app.ml.eval --save     # also store the run in the eval_runs table

Matching: for each of the 20 seed resumes (parsed from their PDFs with the real parser),
all 50 seed jobs are ranked by three methods and compared with the labelled relevant set
in seed/data/eval_pairs.json:
  - tfidf:      TF-IDF cosine, resume text vs job text (lexical baseline)
  - embeddings: all-MiniLM-L6-v2 cosine only
  - hike:       the full match score (semantic + skills + experience + location)
Metrics: precision@5, recall@5, MRR, and accuracy of the "top-5 = relevant" decision over
all 1,000 pairs.

Classifier: 5-fold stratified cross-validation on the synthetic training set, plus accuracy
on the 20 seed resumes, which the model never sees during training.

Nothing here is hard-coded: every number is computed from the data on each run.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from app.ml.classifier import CATEGORIES, RoleClassifier, build_pipeline, load_training_data
from app.ml.embeddings import embed_documents
from app.ml.tfidf import TfidfMatcher

BACKEND_DIR = Path(__file__).resolve().parents[2]
SEED_DIR = BACKEND_DIR / "seed"
RESULTS_PATH = Path(__file__).parent / "eval_results.json"
K = 5


def load_seed() -> tuple[list[dict], list[dict], dict[str, set[int]]]:
    jobs = json.loads((SEED_DIR / "data" / "jobs.json").read_text(encoding="utf-8"))
    resumes = json.loads((SEED_DIR / "data" / "resumes.json").read_text(encoding="utf-8"))
    pairs = json.loads((SEED_DIR / "data" / "eval_pairs.json").read_text(encoding="utf-8"))
    labels = {p["resume"]: set(p["relevant_jobs"]) for p in pairs["pairs"]}
    return jobs, resumes, labels


def parse_seed_resumes(resumes: list[dict]) -> list[dict]:
    from app.services.resume_parser import extract_text, parse_resume

    out = []
    for r in resumes:
        text = extract_text((SEED_DIR / "resumes" / r["file"]).read_bytes(), "pdf")
        out.append(
            {
                "file": r["file"],
                "category": r["category"],
                "text": text,
                "parsed": parse_resume(text),
            }
        )
    return out


def ranking_metrics(scores: np.ndarray, job_keys: list[int], relevant: list[set[int]]) -> dict:
    """scores: (n_resumes, n_jobs). Higher = better."""
    p_at_k, r_at_k, rr = [], [], []
    correct = total = 0
    for i, rel in enumerate(relevant):
        order = np.argsort(-scores[i], kind="stable")
        ranked = [job_keys[j] for j in order]
        top = set(ranked[:K])
        hits = len(top & rel)
        p_at_k.append(hits / K)
        r_at_k.append(hits / len(rel))
        first = next((pos for pos, key in enumerate(ranked, 1) if key in rel), None)
        rr.append(1 / first if first else 0.0)
        for key in job_keys:
            correct += (key in top) == (key in rel)
            total += 1
    return {
        "precision_at_5": round(float(np.mean(p_at_k)), 4),
        "recall_at_5": round(float(np.mean(r_at_k)), 4),
        "mrr": round(float(np.mean(rr)), 4),
        "accuracy": round(correct / total, 4),
    }


def evaluate_matching(jobs, parsed_resumes, labels) -> dict:
    from app.services.matching import JobSide, ResumeSide, compute_match, job_text

    job_keys = [j["key"] for j in jobs]
    job_texts = [job_text(j["title"], j["skills"], j["description_md"]) for j in jobs]
    resume_texts = [r["text"] for r in parsed_resumes]
    relevant = [labels[r["file"]] for r in parsed_resumes]

    tfidf = TfidfMatcher().fit(job_texts + resume_texts)
    tfidf_scores = tfidf.similarity(resume_texts, job_texts)

    job_vecs = embed_documents(job_texts)
    res_vecs = embed_documents(resume_texts)
    cos = res_vecs @ job_vecs.T

    hike = np.zeros_like(cos)
    for i, r in enumerate(parsed_resumes):
        p = r["parsed"]
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
            hike[i, j] = compute_match(side, js)["score"]

    rel_mask = np.array([[k in rel for k in job_keys] for rel in relevant])
    return {
        "n_resumes": len(parsed_resumes),
        "n_jobs": len(jobs),
        "n_relevant_pairs": int(rel_mask.sum()),
        "methods": {
            "tfidf": ranking_metrics(tfidf_scores, job_keys, relevant),
            "embeddings": ranking_metrics(cos, job_keys, relevant),
            "hike": ranking_metrics(hike, job_keys, relevant),
        },
        # Used to choose SEM_FLOOR / SEM_CEIL in services/matching.py.
        "cosine_distribution": {
            "relevant": _quantiles(cos[rel_mask]),
            "not_relevant": _quantiles(cos[~rel_mask]),
        },
    }


def _quantiles(x: np.ndarray) -> dict:
    q = np.quantile(x, [0.05, 0.5, 0.95])
    return {
        "p05": round(float(q[0]), 3),
        "median": round(float(q[1]), 3),
        "p95": round(float(q[2]), 3),
    }


def evaluate_classifier(parsed_resumes) -> dict:
    texts, labels = load_training_data()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    cv_pred = cross_val_predict(build_pipeline(), texts, labels, cv=cv)
    model = RoleClassifier.train(texts, labels)
    y_true = [r["category"] for r in parsed_resumes]
    y_pred = model.predict_many([r["text"] for r in parsed_resumes])
    return {
        "labels": CATEGORIES,
        "cv_synthetic": {
            "n": len(texts),
            "accuracy": round(accuracy_score(labels, cv_pred), 4),
            "macro_f1": round(f1_score(labels, cv_pred, average="macro"), 4),
            "confusion_matrix": confusion_matrix(labels, cv_pred, labels=CATEGORIES).tolist(),
        },
        "seed_resumes": {
            "n": len(y_true),
            "accuracy": round(accuracy_score(y_true, y_pred), 4),
            "confusion_matrix": confusion_matrix(y_true, y_pred, labels=CATEGORIES).tolist(),
            "errors": [
                {"resume": r["file"], "true": t, "pred": p}
                for r, t, p in zip(parsed_resumes, y_true, y_pred, strict=True)
                if t != p
            ],
        },
    }


def git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BACKEND_DIR,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def run() -> dict:
    jobs, resumes, labels = load_seed()
    parsed = parse_seed_resumes(resumes)
    return {
        "matching": evaluate_matching(jobs, parsed, labels),
        "classifier": evaluate_classifier(parsed),
    }


def save_to_db(metrics: dict) -> None:
    from app.db.session import SessionLocal
    from app.models import EvalRun

    with SessionLocal() as db:
        db.add(EvalRun(git_sha=git_sha(), metrics=metrics))
        db.commit()


def print_report(m: dict) -> None:
    mt = m["matching"]
    print(
        f"\nMatching: {mt['n_resumes']} resumes x {mt['n_jobs']} jobs, "
        f"{mt['n_relevant_pairs']} relevant pairs"
    )
    print(f"{'method':<12}{'P@5':>8}{'R@5':>8}{'MRR':>8}{'Acc':>8}")
    for name, r in mt["methods"].items():
        print(
            f"{name:<12}{r['precision_at_5']:>8.3f}{r['recall_at_5']:>8.3f}"
            f"{r['mrr']:>8.3f}{r['accuracy']:>8.3f}"
        )
    cd = mt["cosine_distribution"]
    print(f"MiniLM cosine  relevant {cd['relevant']}  not relevant {cd['not_relevant']}")
    c = m["classifier"]
    print(
        f"\nClassifier 5-fold CV on {c['cv_synthetic']['n']} synthetic samples: "
        f"accuracy {c['cv_synthetic']['accuracy']:.3f}, macro F1 {c['cv_synthetic']['macro_f1']:.3f}"
    )
    s = c["seed_resumes"]
    print(f"Classifier on {s['n']} held-out seed resumes: accuracy {s['accuracy']:.3f}")
    print("Confusion matrix (rows = true, cols = predicted):", c["labels"])
    for label, row in zip(c["labels"], s["confusion_matrix"], strict=True):
        print(f"  {label:<10} {row}")
    for e in s["errors"]:
        print(f"  misclassified: {e['resume']} true={e['true']} pred={e['pred']}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--save", action="store_true", help="store results in the eval_runs table")
    args = ap.parse_args(argv)
    metrics = run()
    RESULTS_PATH.write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    print_report(metrics)
    if args.save:
        save_to_db(metrics)
        print("\nsaved to eval_runs")


if __name__ == "__main__":
    main(sys.argv[1:])
