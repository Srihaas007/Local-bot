from __future__ import annotations
from src.local_agent.tools.web_fetch import WebFetch

def test_web_fetch_denied_by_default():
    t = WebFetch()
    r = t.run(url="https://example.com/")
    assert not r.ok
    msg = r.content.lower()
    # Accept either policy denial or missing dependency message
    assert ("not allowed" in msg) or ("only http/https" in msg) or ("blocked content-type" in msg) or ("missing dependency" in msg)
