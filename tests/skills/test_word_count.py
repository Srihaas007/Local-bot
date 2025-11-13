
from __future__ import annotations
from src.local_agent.tools.generated.word_count import WordCountTool

def test_word_count_tool():
    t = WordCountTool()
    r = t.run(text="hello world")
    assert r.ok and r.content == "2"
