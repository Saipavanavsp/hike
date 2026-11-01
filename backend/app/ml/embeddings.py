"""Sentence embeddings with all-MiniLM-L6-v2 (384 dims, L2-normalised).

Two interchangeable backends:
- OnnxEmbedder (default, production): onnxruntime + HF tokenizers, ~150 MB RAM, no torch.
- SentenceTransformerEmbedder (reference): the sentence-transformers library itself.
tests/test_embeddings.py checks both produce the same vectors.

Long documents are split into ~180-word windows (the model truncates at 256 word pieces),
each window is embedded and the mean vector is re-normalised.
"""

import hashlib
import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np

from app.core.config import settings

log = logging.getLogger(__name__)

MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384
MAX_TOKENS = 256
WINDOW_WORDS = 180
MAX_WINDOWS = 8


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


def _l2_normalise(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.clip(norms, 1e-12, None)


class OnnxEmbedder:
    def __init__(self, model_dir: str = ""):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_path, tok_path = self._resolve_files(model_dir)
        self.tokenizer = Tokenizer.from_file(str(tok_path))
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(
            str(model_path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self.input_names = {i.name for i in self.session.get_inputs()}
        self._lock = threading.Lock()

    @staticmethod
    def _resolve_files(model_dir: str) -> tuple[Path, Path]:
        if model_dir and (Path(model_dir) / "model.onnx").exists():
            return Path(model_dir) / "model.onnx", Path(model_dir) / "tokenizer.json"
        from huggingface_hub import hf_hub_download

        return (
            Path(hf_hub_download(MODEL_REPO, "onnx/model.onnx")),
            Path(hf_hub_download(MODEL_REPO, "tokenizer.json")),
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIM), dtype=np.float32)
        enc = self.tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)
        with self._lock:
            hidden = self.session.run(None, feeds)[0]  # (batch, seq, 384)
        # Mean pooling over real tokens, exactly like sentence-transformers' Pooling layer.
        m = mask[..., None].astype(np.float32)
        pooled = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        return _l2_normalise(pooled).astype(np.float32)


class SentenceTransformerEmbedder:
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(MODEL_REPO, device="cpu")
        self.model.max_seq_length = MAX_TOKENS

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True).astype(
            np.float32
        )


@lru_cache
def get_embedder() -> Embedder:
    backend = settings.embedding_backend
    log.info("loading embedding model (%s backend)", backend)
    if backend == "sentence-transformers":
        return SentenceTransformerEmbedder()
    return OnnxEmbedder(settings.model_dir)


def windows(text: str) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    chunks = [" ".join(words[i : i + WINDOW_WORDS]) for i in range(0, len(words), WINDOW_WORDS)]
    return chunks[:MAX_WINDOWS]


def embed_documents(texts: list[str], embedder: Embedder | None = None) -> np.ndarray:
    """One normalised vector per document (mean of its window embeddings)."""
    embedder = embedder or get_embedder()
    all_windows, owners = [], []
    for i, t in enumerate(texts):
        for w in windows(t):
            all_windows.append(w)
            owners.append(i)
    vecs = embedder.encode(all_windows)
    out = np.zeros((len(texts), DIM), dtype=np.float32)
    counts = np.zeros(len(texts), dtype=np.float32)
    for vec, owner in zip(vecs, owners, strict=True):
        out[owner] += vec
        counts[owner] += 1
    out /= np.clip(counts[:, None], 1, None)
    return _l2_normalise(out)


def embed_document(text: str) -> np.ndarray:
    return embed_documents([text])[0]


def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()
