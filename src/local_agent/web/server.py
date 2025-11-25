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
from ..config import FLAGS
from ..memory import MemoryStore, MemoryItem
from ..model_providers.echo_provider import EchoProvider
try:  # optional providers
    from ..model_providers.llama_cpp_provider import LlamaCppProvider  # type: ignore
except Exception:  # pragma: no cover
    LlamaCppProvider = None  # type: ignore
try:
    from ..model_providers.transformers_provider import TransformersProvider  # type: ignore
except Exception:  # pragma: no cover
    TransformersProvider = None  # type: ignore
from ..tools import Tool, TextToSpeechTool, SpeechToTextTool
from ..tools.run_python import RunPython
from ..tools.file_tools import ReadFile, WriteFile
from ..config import WORKSPACE
from ..memory.sqlite_memory import MemoryItem


app = FastAPI(title="Local Agent Server", version="0.1.0")

# Global single agent instance (Echo by default). For extensibility, swap provider via env/config later.
# Auto-approve tools in web server context so the agent can act without manual prompts
FLAGS.approve_tools = False
AGENT = Agent(EchoProvider(), memory=MemoryStore())

# Simple in-memory download job registry (not persistent)
_DOWNLOAD_JOBS: dict[str, dict] = {}
import threading, requests, time

def _stream_download(job_id: str, url: str, out_path: Path) -> None:
    _DOWNLOAD_JOBS[job_id]["status"] = "downloading"
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0))
            _DOWNLOAD_JOBS[job_id]["total"] = total
            downloaded = 0
            chunk_size = 1 << 15  # 32KB
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    _DOWNLOAD_JOBS[job_id]["downloaded"] = downloaded
            _DOWNLOAD_JOBS[job_id]["status"] = "finished"
    except Exception as e:
        _DOWNLOAD_JOBS[job_id]["status"] = "error"
        _DOWNLOAD_JOBS[job_id]["error"] = str(e)
    finally:
        _DOWNLOAD_JOBS[job_id]["ended"] = time.time()

def _hf_download(job_id: str, model_name: str, filename: str, out_path: Path) -> None:
    _DOWNLOAD_JOBS[job_id]["status"] = "downloading"
    try:
        try:
            from huggingface_hub import hf_hub_download  # type: ignore
        except Exception:
            raise RuntimeError("huggingface_hub not installed: pip install huggingface_hub")
        # hf_hub_download returns local cached path
        local_path = hf_hub_download(repo_id=model_name, filename=filename)
        # copy to out_path
        out_path.write_bytes(Path(local_path).read_bytes())
        size = out_path.stat().st_size
        _DOWNLOAD_JOBS[job_id]["total"] = size
        _DOWNLOAD_JOBS[job_id]["downloaded"] = size
        _DOWNLOAD_JOBS[job_id]["status"] = "finished"
    except Exception as e:
        _DOWNLOAD_JOBS[job_id]["status"] = "error"
        _DOWNLOAD_JOBS[job_id]["error"] = str(e)
    finally:
        _DOWNLOAD_JOBS[job_id]["ended"] = time.time()

def _make_provider(name: str, model_path: str | None = None, model_name: str | None = None):
    name = name.lower()
    if name == "echo":
        return EchoProvider()
    if name in {"llamacpp", "llama", "llama_cpp"}:
        if not LlamaCppProvider:
            raise RuntimeError("llama-cpp-python not installed")
        if not model_path:
            raise RuntimeError("model_path required for llama.cpp provider")
        return LlamaCppProvider(model_path=model_path)
    if name in {"transformers", "hf"}:
        if not TransformersProvider:
            raise RuntimeError("transformers not installed")
        if not model_name:
            raise RuntimeError("model_name required for transformers provider")
        return TransformersProvider(model_name=model_name)
    raise RuntimeError(f"Unknown provider: {name}")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/provider/list")
def provider_list() -> JSONResponse:
    providers = ["echo"]
    if LlamaCppProvider:
        providers.append("llamacpp")
    if TransformersProvider:
        providers.append("transformers")
    return JSONResponse({"providers": providers, "active": type(AGENT.provider).__name__})


@app.post("/provider/set")
def provider_set(payload: dict) -> JSONResponse:
    name = str(payload.get("name", "")).strip()
    model_path = payload.get("model_path")
    model_name = payload.get("model_name")
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    global AGENT
    try:
        prov = _make_provider(name, model_path=model_path, model_name=model_name)
        # preserve memory state
        mem = AGENT.memory
        AGENT = Agent(prov, memory=mem)
        return JSONResponse({"ok": True, "active": type(AGENT.provider).__name__})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.get("/tools")
def tools_list() -> JSONResponse:
    # Tools registered on agent
    schemas = []
    for t in AGENT.tools:
        try:
            schemas.append(t.schema())
        except Exception:
            schemas.append({"name": getattr(t, "name", "unknown"), "error": "schema failed"})
    return JSONResponse({"tools": schemas})


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


@app.post("/memory/save")
def memory_save(payload: dict) -> JSONResponse:
    text = str(payload.get("text", "")).strip()
    kind = str(payload.get("kind", "note")).strip() or "note"
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    # Use embedding path automatically if provider available
    try:
        count = AGENT.memory.add([MemoryItem(kind=kind, text=text)])
        return JSONResponse({"ok": True, "count": count})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/memory/list")
def memory_list(limit: int = Query(500)) -> JSONResponse:
    # simple recent listing
    import sqlite3
    con = sqlite3.connect(AGENT.memory.db_path)
    try:
        cur = con.execute("SELECT id, kind, text, ts FROM memories ORDER BY id DESC LIMIT ?", (limit,))
        rows = [
            {"id": r[0], "kind": r[1], "text": r[2], "ts": r[3]} for r in cur
        ]
        return JSONResponse({"memories": rows})
    finally:
        con.close()


@app.post("/model/download")
def model_download(payload: dict) -> JSONResponse:
    """Start a background model download.
    Payload options:
      {"url": "https://.../model.gguf", "filename": "my.gguf"}
      OR {"hf_model": "org/model", "filename": "model-file.bin"}
    Returns job_id for polling /model/status/{job_id}
    """
    url = payload.get("url")
    hf_model = payload.get("hf_model")
    filename = payload.get("filename") or (Path(url).name if url else None)
    if not filename:
        return JSONResponse({"error": "filename required"}, status_code=400)
    safe_name = filename.replace("..", "_")
    out_path = Path("models") / safe_name
    job_id = str(int(time.time()*1000))
    _DOWNLOAD_JOBS[job_id] = {"status": "pending", "created": time.time(), "file": str(out_path)}
    if url:
        t = threading.Thread(target=_stream_download, args=(job_id, url, out_path), daemon=True)
        t.start()
    elif hf_model:
        t = threading.Thread(target=_hf_download, args=(job_id, hf_model, safe_name, out_path), daemon=True)
        t.start()
    else:
        return JSONResponse({"error": "Either url or hf_model required"}, status_code=400)
    return JSONResponse({"ok": True, "job_id": job_id, "file": str(out_path)})


@app.get("/model/status/{job_id}")
def model_status(job_id: str) -> JSONResponse:
    job = _DOWNLOAD_JOBS.get(job_id)
    if not job:
        return JSONResponse({"error": "unknown job"}, status_code=404)
    return JSONResponse(job)


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


@app.post("/run_python")
def run_python(payload: dict) -> JSONResponse:
    code = str(payload.get("code", ""))
    if not code.strip():
        return JSONResponse({"ok": False, "error": "code required"}, status_code=400)
    tool = RunPython()
    r = tool.run(
        code=code,
        args=list(payload.get("args", []) or []),
        timeout=int(payload.get("timeout", 10)),
        restricted=bool(payload.get("restricted", True)),
        keep=bool(payload.get("keep", False)),
        stdin=str(payload.get("stdin", "")),
    )
    return JSONResponse({"ok": r.ok, "content": r.content})


@app.post("/orchestrate")
def orchestrate(payload: dict) -> JSONResponse:
    task = str(payload.get("task", ""))
    if not task:
        return JSONResponse({"error": "task required"}, status_code=400)
    
    from ..orchestrator import Orchestrator
    # Create a fresh orchestrator for this request (or could be global if we want to track state)
    # For now, stateless per request (blocking)
    orch = Orchestrator(AGENT, max_steps=10)
    history = orch.run_task(task)
    
    # Convert history to JSON-serializable format
    steps = []
    for step in history:
        steps.append({
            "step": step.step,
            "action": step.action,
            "output": step.output
        })
        
    return JSONResponse({"history": steps})


@app.get("/fs/read")
def fs_read(path: str = Query(""), start: int = Query(1), end: int = Query(10000)) -> JSONResponse:
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    tool = ReadFile()
    r = tool.run(path=path, start=start, end=end)
    return JSONResponse({"ok": r.ok, "content": r.content})


@app.post("/fs/write")
def fs_write(payload: dict) -> JSONResponse:
    path = str(payload.get("path", ""))
    content = str(payload.get("content", ""))
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    tool = WriteFile()
    r = tool.run(path=path, content=content)
    return JSONResponse({"ok": r.ok, "content": r.content})


@app.post("/fs/upload")
def fs_upload(file: UploadFile = File(...), dest: str | None = None) -> JSONResponse:
    try:
        # default to uploads/<filename> inside workspace
        rel = Path(dest) if dest else Path("uploads") / Path(file.filename).name
        abs_path = (WORKSPACE / rel).resolve()
        # jail
        if not str(abs_path).startswith(str(WORKSPACE.resolve())):
            return JSONResponse({"error": "dest escapes workspace"}, status_code=400)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        data = file.file.read()
        abs_path.write_bytes(data)
        return JSONResponse({"ok": True, "path": str(rel).replace("\\", "/")})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


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