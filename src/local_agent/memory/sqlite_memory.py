from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple, Optional
from ..config import MEMORY_DB
from .embeddings import EmbeddingsProvider


@dataclass
class MemoryItem:
    kind: str
    text: str


class MemoryStore:
    def __init__(self, db_path: Path = MEMORY_DB, embedder: Optional[EmbeddingsProvider] = None) -> None:
        self.db_path = db_path
        self.embedder = embedder or EmbeddingsProvider()
        self._init_db()

    def _init_db(self) -> None:
        con = sqlite3.connect(self.db_path)
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS mem_vectors (
                    id INTEGER PRIMARY KEY,
                    dim INTEGER NOT NULL,
                    vec BLOB NOT NULL,
                    FOREIGN KEY (id) REFERENCES memories(id) ON DELETE CASCADE
                )
                """
            )
            con.commit()
        finally:
            con.close()

    def add(self, items: Iterable[MemoryItem]) -> int:
        con = sqlite3.connect(self.db_path)
        try:
            cur = con.executemany("INSERT INTO memories(kind, text) VALUES (?, ?)", ((i.kind, i.text) for i in items))
            con.commit()
            return cur.rowcount or 0
        finally:
            con.close()

    def add_with_embeddings(self, items: Iterable[MemoryItem]) -> int:
        # Insert rows, then compute embeddings if available and store as BLOB (float32)
        items_list = list(items)
        if not items_list:
            return 0
        con = sqlite3.connect(self.db_path)
        try:
            cur = con.executemany("INSERT INTO memories(kind, text) VALUES (?, ?)", ((i.kind, i.text) for i in items_list))
            con.commit()
            # Fetch last inserted rowids for the batch
            # SQLite doesn't give all rowids directly; reselect by ordering.
            count = cur.rowcount or len(items_list)
            cur2 = con.execute("SELECT id, text FROM memories ORDER BY id DESC LIMIT ?", (count,))
            rows = list(reversed(cur2.fetchall()))  # reverse to original order
            if self.embedder.enabled:
                texts = [t for (_id, t) in rows]
                vecs = self.embedder.embed(texts)
                if vecs is not None:
                    import numpy as np  # type: ignore
                    for (mem_id, _), v in zip(rows, vecs):
                        vec = np.asarray(v, dtype=np.float32)
                        con.execute(
                            "INSERT OR REPLACE INTO mem_vectors(id, dim, vec) VALUES (?, ?, ?)",
                            (mem_id, int(vec.shape[0]), vec.tobytes()),
                        )
                    con.commit()
            return count
        finally:
            con.close()

    def search_keyword(self, query: str, limit: int = 10) -> List[Tuple[int, str, str]]:
        con = sqlite3.connect(self.db_path)
        try:
            cur = con.execute(
                "SELECT id, kind, text FROM memories WHERE text LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit),
            )
            return list(cur.fetchall())
        finally:
            con.close()

    def search_semantic(self, query: str, limit: int = 5) -> List[Tuple[int, str, str]]:
        if not self.embedder.enabled:
            return []
        import numpy as np  # type: ignore
        qvecs = self.embedder.embed([query])
        if qvecs is None:
            return []
        q = qvecs[0]
        con = sqlite3.connect(self.db_path)
        try:
            cur = con.execute("SELECT m.id, m.kind, m.text, v.dim, v.vec FROM memories m JOIN mem_vectors v ON m.id=v.id")
            scores: List[Tuple[float, int, str, str]] = []
            for mem_id, kind, text, dim, blob in cur:
                vec = np.frombuffer(blob, dtype=np.float32)
                if vec.shape[0] != dim:
                    continue
                # cosine since vectors are normalized
                score = float(np.dot(q, vec))
                scores.append((score, mem_id, kind, text))
            scores.sort(reverse=True, key=lambda x: x[0])
            top = scores[:limit]
            return [(mem_id, kind, text) for (_s, mem_id, kind, text) in top]
        finally:
            con.close()

    def search(self, query: str, limit: int = 5) -> List[Tuple[int, str, str]]:
        # Try semantic first, then fall back to keyword.
        hits = self.search_semantic(query, limit)
        if hits:
            return hits
        return self.search_keyword(query, limit)
