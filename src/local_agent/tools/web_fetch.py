from __future__ import annotations
from typing import Any, Dict
from urllib.parse import urlparse
from .base import Tool, ToolResult
from ..config import FLAGS


class WebFetch(Tool):
    name = "web_fetch"
    description = "Fetch a URL over HTTP(S) with domain allowlist, size/time limits"

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "timeout": {"type": "integer", "default": 10},
                    "max_bytes": {"type": "integer", "default": 500_000}
                },
                "required": ["url"],
            },
        }

    def run(self, **kwargs: Any) -> ToolResult:
        try:
            import requests  # type: ignore
        except Exception:
            return ToolResult(ok=False, content="Missing dependency: pip install requests")
        url = kwargs.get("url", "")
        timeout = int(kwargs.get("timeout", 10))
        max_bytes = int(kwargs.get("max_bytes", 500_000))
        try:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                return ToolResult(ok=False, content="Only http/https schemes are allowed")
            host = (parsed.hostname or "").lower()
            if not host:
                return ToolResult(ok=False, content="Invalid URL")
            if FLAGS.allowed_domains and host not in FLAGS.allowed_domains:
                return ToolResult(ok=False, content=f"Domain '{host}' not allowed. Set LOCAL_AGENT_ALLOWED_DOMAINS to include it.")
            # Fetch with streaming and cap size
            try:
                r = requests.get(url, timeout=timeout, stream=True)
            except Exception as e:
                return ToolResult(ok=False, content=f"Request error: {e}")
            ctype = r.headers.get("Content-Type", "")
            # restrict to text
            if "text/" not in ctype and "json" not in ctype:
                return ToolResult(ok=False, content=f"Blocked content-type: {ctype}")
            chunks = []
            total = 0
            for chunk in r.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    return ToolResult(ok=False, content=f"Response too large (> {max_bytes} bytes)")
                chunks.append(chunk)
            content = b"".join(chunks).decode(errors="replace")
            return ToolResult(ok=True, content=content)
        except Exception as e:
            return ToolResult(ok=False, content=f"web_fetch error: {e}")
