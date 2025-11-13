from __future__ import annotations
from typing import Iterable, List, Optional

class EmbeddingsProvider:
    """
    Optional embeddings provider. If sentence-transformers is not installed, this becomes a no-op and
    returns None, signalling that semantic memory is disabled.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._np = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            import numpy as np  # type: ignore
            self._model = SentenceTransformer(model_name)
            self._np = np
        except Exception:
            # Not installed; semantic embeddings disabled
            self._model = None
            self._np = None

    @property
    def enabled(self) -> bool:
        return self._model is not None and self._np is not None

    def embed(self, texts: Iterable[str]) -> Optional["np.ndarray"]:  # type: ignore[name-defined]
        if not self.enabled:
            return None
        assert self._model is not None and self._np is not None
        vecs = self._model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        return vecs
