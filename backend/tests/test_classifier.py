from pathlib import Path

from app.ml import classifier as clf_module
from app.ml.classifier import CATEGORIES, RoleClassifier, get_classifier, load_training_data
from app.ml.tfidf import TfidfMatcher
from app.services.resume_parser import extract_text

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name):
    kind = "pdf" if name.endswith(".pdf") else "docx"
    return extract_text((FIXTURES / name).read_bytes(), kind)


def test_training_data_covers_all_categories():
    _, labels = load_training_data()
    assert set(labels) == set(CATEGORIES)
    assert min(labels.count(c) for c in CATEGORIES) >= 30


def test_classifier_predicts_fixture_resumes():
    model = get_classifier()
    assert model.predict(fixture_text("priya_sharma_backend.pdf"))[0] == "backend"
    assert model.predict(fixture_text("arjun_menon_frontend.docx"))[0] == "frontend"
    label, prob = model.predict(fixture_text("kavya_iyer_data.pdf"))
    assert label == "data_ml"
    assert 0 < prob <= 1


def test_classifier_on_short_texts():
    model = get_classifier()
    assert model.predict("Kotlin, Jetpack Compose, Play Store releases")[0] == "mobile"
    assert model.predict("Terraform modules, Kubernetes, Prometheus alerting")[0] == "devops"
    assert model.predict("Selenium regression suites, TestNG, JMeter")[0] == "qa"
    assert model.predict_many(["React and CSS", "Django and Redis"]) == ["frontend", "backend"]


def test_artifact_is_cached_and_reloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(clf_module, "ARTIFACT_DIR", tmp_path)
    get_classifier.cache_clear()
    try:
        first = get_classifier()
        assert len(list(tmp_path.glob("*.joblib"))) == 1
        get_classifier.cache_clear()
        second = get_classifier()  # loaded from disk this time
        assert isinstance(second, RoleClassifier)
        assert (
            first.predict("Flutter and Dart apps")[0] == second.predict("Flutter and Dart apps")[0]
        )
    finally:
        get_classifier.cache_clear()


def test_tfidf_matcher_similarity():
    docs = ["python django postgres api", "kotlin android compose app"]
    m = TfidfMatcher().fit(docs)
    sims = m.similarity(["django api in python"], docs)
    assert sims.shape == (1, 2)
    assert sims[0, 0] > sims[0, 1]
    assert sims.min() >= 0 and sims.max() <= 1 + 1e-9
