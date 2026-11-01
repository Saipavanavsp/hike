"""TF-IDF + cosine similarity: the lexical baseline the embedding matcher is compared against."""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class TfidfMatcher:
    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), sublinear_tf=True, stop_words="english", min_df=1
        )

    def fit(self, corpus: list[str]) -> "TfidfMatcher":
        self.vectorizer.fit(corpus)
        return self

    def similarity(self, queries: list[str], docs: list[str]) -> np.ndarray:
        """(len(queries), len(docs)) cosine similarities. TF-IDF rows are already L2-normalised."""
        q = self.vectorizer.transform(queries)
        d = self.vectorizer.transform(docs)
        return (q @ d.T).toarray()
