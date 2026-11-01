import numpy as np
import pytest

from app.ml.embeddings import (
    DIM,
    OnnxEmbedder,
    content_hash,
    embed_document,
    embed_documents,
    get_embedder,
    windows,
)


def test_vectors_are_normalised_384d():
    v = get_embedder().encode(["Python backend engineer", "React developer"])
    assert v.shape == (2, DIM)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)
    assert get_embedder().encode([]).shape == (0, DIM)


def test_related_texts_are_closer_than_unrelated():
    a, b, c = embed_documents(
        [
            "Backend engineer building REST APIs with Python, Django and PostgreSQL",
            "Python developer for Django services and SQL databases",
            "Android developer shipping Kotlin apps with Jetpack Compose",
        ]
    )
    assert a @ b > a @ c + 0.1


def test_long_documents_use_windows():
    text = " ".join(f"word{i}" for i in range(1000))
    assert len(windows(text)) == 6
    assert windows("") == [""]
    assert windows(" ".join(["x"] * 5000))[-1]  # capped at MAX_WINDOWS, still non-empty
    assert embed_document(text).shape == (DIM,)


def test_content_hash_is_stable():
    assert content_hash("abc") == content_hash("abc")
    assert content_hash("abc") != content_hash("abd")


def test_onnx_matches_sentence_transformers_reference():
    pytest.importorskip("sentence_transformers")
    from app.ml.embeddings import SentenceTransformerEmbedder

    texts = [
        "Senior backend engineer, 5 years of Go and Kubernetes.",
        "We are hiring a QA automation engineer (Selenium, TestNG).",
        "short",
    ]
    onnx = OnnxEmbedder().encode(texts)
    ref = SentenceTransformerEmbedder().encode(texts)
    assert np.abs(onnx - ref).max() < 1e-4
