import numpy as np
import pytest
from sqlalchemy import select

from app.ml import eval as ev
from app.models import EvalRun


def test_ranking_metrics_on_toy_data():
    # Two resumes, six jobs; scores rank jobs 1..6 in a known order.
    keys = [1, 2, 3, 4, 5, 6]
    scores = np.array(
        [
            [0.9, 0.8, 0.7, 0.6, 0.5, 0.1],  # top-5 = 1..5
            [0.1, 0.2, 0.3, 0.4, 0.5, 0.9],  # top-5 = 6,5,4,3,2
        ]
    )
    relevant = [{1, 6}, {1}]
    m = ev.ranking_metrics(scores, keys, relevant)
    assert m["precision_at_5"] == pytest.approx((1 / 5 + 0 / 5) / 2, abs=1e-4)
    assert m["recall_at_5"] == pytest.approx((1 / 2 + 0) / 2, abs=1e-4)
    assert m["mrr"] == pytest.approx((1 / 1 + 1 / 6) / 2, abs=1e-4)
    # resume 0: wrong on job 6 (relevant, not in top5) and jobs 2-5 (in top5, not relevant)
    # resume 1: wrong on job 1 and on jobs 6,5,4,3,2
    assert m["accuracy"] == pytest.approx((1 + 0) / 12, abs=1e-4)


def test_full_eval_run_produces_bounded_metrics(db):
    metrics = ev.run()
    for method in ("tfidf", "embeddings", "hike"):
        r = metrics["matching"]["methods"][method]
        for k in ("precision_at_5", "recall_at_5", "mrr", "accuracy"):
            assert 0.0 <= r[k] <= 1.0
    assert metrics["matching"]["n_resumes"] == 20
    assert metrics["matching"]["n_jobs"] == 50
    cm = np.array(metrics["classifier"]["seed_resumes"]["confusion_matrix"])
    assert cm.sum() == 20

    ev.save_to_db(metrics)
    row = db.scalar(select(EvalRun))
    assert row.metrics["matching"]["n_jobs"] == 50
