"""Typo correction, synonyms, hybrid ranking, and the search relevance evaluation.

Set UPDATE_SEARCH_EVAL=1 to rewrite app/ml/eval_search_results.json and
docs/search-evaluation.md from a freshly seeded test database.
"""

import json
import os
import random

import pytest

from app.ml import eval_search
from app.services import query_understanding as qu
from app.services.ranking import hybrid_text, normalise_text_rank
from seed import seed as seed_module
from tests.factories import make_user
from tests.test_jobs_api import make_job


@pytest.fixture
def jobs(db):
    rec = make_user(db, "rec@example.com", "recruiter")
    make_job(db, rec, title="Python Developer", skills=["Python", "Django"])
    make_job(db, rec, title="Kubernetes Platform Engineer", skills=["Kubernetes", "Helm"])
    make_job(db, rec, title="JavaScript Engineer", skills=["JavaScript", "React"])
    return db


def test_typos_are_corrected_to_job_vocabulary(jobs):
    p = qu.plan(jobs, "pyhton developer")
    assert p.corrected == "python developer"
    assert qu.plan(jobs, "djnago").corrected == "django"
    assert qu.plan(jobs, "kubrenetes").corrected == "kubernetes"
    # "kubernets" needs no correction: English stemming already maps it to "kubernet".
    assert qu.plan(jobs, "kubernets").corrected is None
    # Real words in the corpus, short words and synonyms are left alone.
    assert qu.plan(jobs, "python developer").corrected is None
    assert qu.plan(jobs, "go").corrected is None
    assert qu.plan(jobs, "k8s").corrected is None
    # No close word: kept as typed.
    assert qu.plan(jobs, "zzzzqqq").corrected is None


def test_synonyms_expand_to_or_groups(jobs):
    units = qu.plan(jobs, "js developer").units
    assert units == [["javascript", "js"], ["developer", "engineer"]]
    assert qu.plan(jobs, "front end developer").units[0][0] == "frontend"
    no_syn = qu.plan(jobs, "js developer", use_synonyms=False).units
    assert no_syn == [["js"], ["developer"]]
    # Web-search syntax passes through untouched.
    assert qu.plan(jobs, '"python developer" -django').websearch


def test_search_api_reports_the_correction(client, jobs):
    res = client.get("/api/jobs", params={"q": "pyhton developer"}).json()
    assert res["corrected_query"] == "python developer"
    assert [j["title"] for j in res["items"]][0] == "Python Developer"
    res = client.get("/api/jobs", params={"q": "kubernets"}).json()
    assert res["items"][0]["title"] == "Kubernetes Platform Engineer"
    res = client.get("/api/jobs", params={"q": "k8s"}).json()
    assert res["corrected_query"] is None
    assert res["items"][0]["title"] == "Kubernetes Platform Engineer"


def test_hybrid_text_score():
    assert hybrid_text(1.0, None, 0.4) == normalise_text_rank(1.0)
    assert hybrid_text(1.0, 0.9, 0.0) == normalise_text_rank(1.0)
    assert hybrid_text(0.0, 0.65, 0.4) == pytest.approx(0.4)  # semantic only, fully relevant
    assert hybrid_text(0.0, 0.10, 0.4) == 0.0


def test_search_evaluation_reproduces(db, client):
    seed_module.seed(db, random.Random(7), run_eval=False)
    fresh = eval_search.run(db)
    if os.environ.get("UPDATE_SEARCH_EVAL"):
        eval_search.RESULTS_PATH.write_text(json.dumps(fresh, indent=1), encoding="utf-8")
        eval_search.REPORT_PATH.write_text(eval_search.render(fresh), encoding="utf-8")
    committed = json.loads(eval_search.RESULTS_PATH.read_text(encoding="utf-8"))
    for name, s in committed["configs"].items():
        assert fresh["configs"][name]["ndcg_at_10"]["mean"] == pytest.approx(
            s["ndcg_at_10"]["mean"], abs=0.02
        ), name
    assert eval_search.REPORT_PATH.read_text(encoding="utf-8") == eval_search.render(committed)
    lexical = fresh["configs"]["Lexical (before)"]
    hybrid = fresh["configs"]["Hybrid (production)"]
    assert hybrid["ndcg_at_10"]["mean"] > lexical["ndcg_at_10"]["mean"]
    assert hybrid["by_type"]["typo"] > lexical["by_type"]["typo"] + 0.3
    assert hybrid["zero_results"]["mean"] <= lexical["zero_results"]["mean"]
