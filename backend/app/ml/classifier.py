"""Role-category classifier: TF-IDF (word 1-2 grams) + multinomial logistic regression.

Predicts Backend / Frontend / Full-Stack / Data-ML / DevOps / Mobile / QA from resume text.
Used to tag resumes (shown to recruiters, filterable) and as a small ranking signal.
"""

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

log = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent / "data" / "classifier_train.json"
ARTIFACT_DIR = Path(__file__).parent / "artifacts"
CATEGORIES = ["backend", "frontend", "fullstack", "data_ml", "devops", "mobile", "qa"]
LABELS = {
    "backend": "Backend",
    "frontend": "Frontend",
    "fullstack": "Full-Stack",
    "data_ml": "Data/ML",
    "devops": "DevOps",
    "mobile": "Mobile",
    "qa": "QA",
}


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2), sublinear_tf=True, min_df=1, stop_words="english"
                ),
            ),
            ("clf", LogisticRegression(max_iter=2000, C=4.0)),
        ]
    )


def load_training_data() -> tuple[list[str], list[str]]:
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [r["text"] for r in rows], [r["label"] for r in rows]


class RoleClassifier:
    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline

    @classmethod
    def train(cls, texts: list[str], labels: list[str]) -> "RoleClassifier":
        pipe = build_pipeline()
        pipe.fit(texts, labels)
        return cls(pipe)

    def predict(self, text: str) -> tuple[str, float]:
        probs = self.pipeline.predict_proba([text])[0]
        idx = int(probs.argmax())
        return str(self.pipeline.classes_[idx]), float(probs[idx])

    def predict_many(self, texts: list[str]) -> list[str]:
        return [str(x) for x in self.pipeline.predict(texts)]


def _data_hash() -> str:
    return hashlib.sha1(DATA_PATH.read_bytes()).hexdigest()[:12]


@lru_cache
def get_classifier() -> RoleClassifier:
    """Load the trained model from disk, retraining if the training data changed."""
    path = ARTIFACT_DIR / f"role_classifier_{_data_hash()}.joblib"
    if path.exists():
        try:
            return RoleClassifier(joblib.load(path))
        except Exception:
            log.warning("could not load %s, retraining", path)
    texts, labels = load_training_data()
    model = RoleClassifier.train(texts, labels)
    try:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(model.pipeline, path)
    except OSError:
        log.warning("artifact dir not writable; classifier kept in memory only")
    return model
