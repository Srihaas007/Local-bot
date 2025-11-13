from __future__ import annotations
import json
import os
import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover
    pytest.skip("fastapi not installed", allow_module_level=True)

from src.local_agent.web.server import app


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_chat_basic():
    r = client.post("/chat", json={"message": "Hello"})
    assert r.status_code == 200
    data = r.json()
    assert "output" in data


def test_memory_search_empty():
    r = client.get("/memory/search?q=")
    assert r.status_code == 200
    assert r.json()["hits"] == []
