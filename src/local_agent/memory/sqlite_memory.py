from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple
from ..config import MEMORY_DB


@dataclass
class MemoryItem:
    kind: str
    text: str


class MemoryStore:
    def __init__(self, db_path: Path = MEMORY_DB) -> None:
        self.db_path = db_path
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
