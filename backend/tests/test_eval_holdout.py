import json
import math
from pathlib import Path

import pytest

from app.ml import eval_holdout as eh
from app.ml.eval_report import render

RESULTS = json.loads(eh.RESULTS_PATH.read_text(encoding="utf-8"))


# ---------- metric functions ----------


def test_ndcg_on_toy_ranking():
    grades = {"a": 2, "b": 1}
    assert eh.ndcg_at_k(["a", "b", "x"], grades) == pytest.approx(1.0)
    # Swapping the two relevant jobs: DCG = 1/1 + 3/log2(3); ideal = 3/1 + 1/log2(3).
    expected = (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3))
    assert eh.ndcg_at_k(["b", "a", "x"], grades) == pytest.approx(expected)
    assert eh.ndcg_at_k(["x", "y", "z", "w", "v", "a"], grades) == 0.0
    assert eh.ndcg_at_k(["a"], {}) == 0.0


def test_per_resume_metrics():
    m = eh.per_resume_metrics(["x", "a", "y", "z", "w", "b"], {"a": 2, "b": 1})
    assert m["p_at_5"] == pytest.approx(1 / 5)
    assert m["r_at_5"] == pytest.approx(1 / 2)
    assert m["mrr"] == pytest.approx(1 / 2)


def test_bootstrap_is_deterministic_and_brackets_the_mean():
    values = [0.2, 0.4, 0.6, 0.8, 1.0, 0.0]
    lo, hi = eh.bootstrap_ci(values)
    assert lo <= sum(values) / len(values) <= hi
    assert eh.bootstrap_ci(values) == [lo, hi]
    assert eh.bootstrap_ci([0.5] * 10) == [0.5, 0.5]


def test_gold_years_merges_overlaps_and_present():
    exp = [
        {"dates": "Jan 2020 - Dec 2020"},
        {"dates": "Jun 2020 - Jun 2021"},  # overlaps the first
        {"dates": "Jan 2026 - Present"},  # to Nov 2026 (fixed evaluation date)
    ]
    assert eh.gold_years(exp) == pytest.approx((18 + 11) / 12, abs=0.05)


# ---------- dataset integrity ----------


def test_dataset_is_consistent():
    jobs, resumes, labels = eh.load()
    job_keys = {j["key"] for j in jobs}
    assert len(job_keys) == len(jobs) == 34
    assert len(resumes) == 24
    for r in resumes:
        path = eh.DATA_DIR / "files" / f"{r['key']}.{eh.EXT[r['format']]}"
        assert path.exists(), path
        assert labels[r["key"]], f"{r['key']} has no relevant job"
        assert set(labels[r["key"]]) <= job_keys
        assert set(labels[r["key"]].values()) <= {1, 2}
        assert r["email"].endswith("@example.com")
    # Every resume layout is used by the same number of resumes.
    formats = [r["format"] for r in resumes]
    assert {formats.count(f) for f in eh.EXT} == {6}
    assert len(list((eh.DATA_DIR / "variants").iterdir())) == 24


def test_label_export_import_round_trip(tmp_path, monkeypatch):
    data_dir = tmp_path / "holdout"
    data_dir.mkdir()
    for name in ("jobs.json", "resumes.json", "labels.json"):
        (data_dir / name).write_text(
            (eh.DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    monkeypatch.setattr(eh, "DATA_DIR", data_dir)
    csv_path = tmp_path / "labels.csv"
    eh.export_labels(csv_path)
    rows = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1 + 24 * 34
    # A reviewer downgrades one pair.
    target = next(i for i, line in enumerate(rows) if line.startswith("r01,") and ",j01," in line)
    assert rows[target].endswith(",2")
    edited = list(rows)
    edited[target] = rows[target][:-1] + "1"
    csv_path.write_text("\n".join(edited) + "\n", encoding="utf-8")
    eh.import_labels(csv_path)
    _, _, labels = eh.load()
    assert labels["r01"]["j01"] == 1
    assert (
        "Reviewed labels imported"
        in json.loads((data_dir / "labels.json").read_text(encoding="utf-8"))["provenance"]
    )


# ---------- the committed numbers are reproducible ----------


@pytest.fixture(scope="module")
def fresh():
    return eh.run()


def test_committed_results_match_a_fresh_run(fresh):
    for method in eh.METHODS:
        for metric in ("p_at_5", "r_at_5", "mrr", "ndcg_at_5"):
            assert fresh["methods"][method][metric]["mean"] == pytest.approx(
                RESULTS["methods"][method][metric]["mean"], abs=0.01
            ), (method, metric)
    assert fresh["dataset"] == RESULTS["dataset"]


def test_report_is_generated_from_the_committed_results():
    doc = (Path(eh.REPORT_PATH)).read_text(encoding="utf-8")
    assert doc == render(RESULTS), "docs/evaluation.md is stale: rerun with --report"


def test_name_and_institution_do_not_move_scores(fresh):
    """Regression guard for the bias found by the counterfactual check."""
    after = fresh["counterfactual_fairness"]["with_redaction"]
    before = fresh["counterfactual_fairness"]["without_redaction"]
    assert after["name"]["max_abs_change_points"] == 0
    assert after["name"]["top5_changed_share"] == 0
    assert after["institution"]["top5_changed_share"] == 0
    assert after["institution"]["mean_abs_change_points"] <= 0.1
    # The check itself is sensitive: without redaction it does detect the effect.
    assert before["name"]["max_abs_change_points"] > 0


def test_report_wording_follows_the_intervals():
    from app.ml.eval_report import _verdict

    assert "no clear difference" in _verdict({"mean": 0.01, "ci95": [-0.01, 0.03]}, "X")
    assert "Hike is better" in _verdict({"mean": 0.05, "ci95": [0.01, 0.09]}, "X")
    assert "X is better" in _verdict({"mean": -0.05, "ci95": [-0.09, -0.01]}, "X")
