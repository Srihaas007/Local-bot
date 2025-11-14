from __future__ import annotations
"""FastAPI server exposing chat, streaming, memory search, and voice mode endpoints.

Endpoints:
  POST /chat            -> JSON chat; auto-approves tools for simplicity
  GET  /chat/stream     -> SSE stream of tokens (data: <chunk>) and final status
  GET  /memory/search?q -> Memory hits
  GET  /tts?text=...    -> Generates WAV via TextToSpeechTool (if dependency available)
  POST /stt             -> Transcribe uploaded WAV via SpeechToTextTool
  GET  /health          -> Basic health check

Static UI served from / (index.html in same directory's 'static').
"""

import io
import json
import mimetypes
import tempfile
from pathlib import Path
from typing import List
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse, FileResponse, HTMLResponse

from ..agent import Agent
from ..memory import MemoryStore, MemoryItem
from ..model_providers.echo_provider import EchoProvider
from ..tools import Tool, TextToSpeechTool, SpeechToTextTool


app = FastAPI(title="Local Agent Server", version="0.1.0")

# Global single agent instance (Echo by default). For extensibility, swap provider via env/config later.
AGENT = Agent(EchoProvider(), memory=MemoryStore())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
def chat(payload: dict) -> JSONResponse:
    message = str(payload.get("message", ""))
    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    # Auto-approve tools in server context for simplicity (could expose flag)
    # Use agent.step (non-stream) for predictable JSON response
    res = AGENT.step(message)
    return JSONResponse({"output": res.output, "used_tool": res.used_tool})


@app.get("/chat/stream")
def chat_stream(message: str = Query("")):
    if not message:
        return PlainTextResponse("message query param required", status_code=400)

    def _gen():
        try:
            for chunk in AGENT.step_stream(message):
                if chunk:
                    yield f"data: {chunk}\n\n"
            # After streaming, if pending tool approval is required, we signal that state
            if getattr(AGENT, "_pending_action", None) is not None:
                name = AGENT._pending_action.get("name")  # type: ignore
                yield f"event: tool\ndata: {json.dumps({'name': name})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/memory/search")
def memory_search(q: str = Query(""), limit: int = Query(5)) -> JSONResponse:
    if not q:
        return JSONResponse({"hits": []})
    hits = AGENT.memory.search(q, limit=limit)
    # hits: list of tuples (id, kind, text)
    return JSONResponse({"hits": [{"id": h[0], "kind": h[1], "text": h[2]} for h in hits]})


@app.get("/tts")
def tts(text: str = Query("")):
    if not text:
        return PlainTextResponse("text query param required", status_code=400)
    try:
        t = TextToSpeechTool()
        # Use a stable output path inside .agent_data to avoid race with temp cleanup
        out_dir = Path(".agent_data") / "tts"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "last_tts.wav"
        r = t.run(text=text, out_path=str(out))
        if not r.ok:
            return PlainTextResponse(r.content, status_code=500)
        if not out.exists() or out.stat().st_size == 0:
            return PlainTextResponse("TTS completed but output file not found or empty", status_code=500)
        return FileResponse(str(out), media_type="audio/wav", filename="tts.wav")
    except Exception as e:
        return PlainTextResponse(f"TTS error: {e}", status_code=500)


@app.post("/stt")
def stt(file: UploadFile = File(...)) -> JSONResponse:
    # Expect a WAV file
    try:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in {".wav"}:
            return JSONResponse({"error": "Only .wav supported"}, status_code=400)
        data = file.file.read()
        with tempfile.TemporaryDirectory() as td:
            fpath = Path(td) / file.filename
            fpath.write_bytes(data)
            tool = SpeechToTextTool()
            r = tool.run(audio_path=str(fpath))
            return JSONResponse({"ok": r.ok, "content": r.content})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


STATIC_DIR = Path(__file__).parent / "static"

@app.get("/")
def index() -> HTMLResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>UI missing</h1>")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


# Minimal static file fallback (CSS/JS assets if added later)
@app.get("/static/{path:path}")
def static_files(path: str):
    f = STATIC_DIR / path
    if not f.exists() or not f.is_file():
        return PlainTextResponse("Not found", status_code=404)
    mt = mimetypes.guess_type(str(f))[0] or "text/plain"
    return FileResponse(str(f), media_type=mt)


def get_app() -> FastAPI:  # convenient factory
    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run("src.local_agent.web.server:app", host="127.0.0.1", port=8000, reload=False)