"""
claude_bridge.py
FastAPI router — POST /chat  (SSE streaming with model routing)
                 GET  /model_stats

Routes messages through model_router.py (Claude API or Qwen3/Ollama).
Logs every call to SQLite for cost/usage tracking.
"""

import json
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from model_router import route_task, classify_task, OLLAMA_MODEL
from history_store import HistoryStore

router   = APIRouter()
_history = HistoryStore()


class ChatRequest(BaseModel):
    message:     str
    force_model: str = "auto"   # "auto" | "claude" | "ollama"
    context:     Optional[str] = ""


@router.post("/chat")
async def chat(req: ChatRequest):
    """
    SSE streaming chat with intelligent model routing.

    Response — one JSON object per line, prefixed 'data: ':
      data: {"type": "routing",  "model": "Qwen3-Coder (...)", "task_type": "coding"}
      data: {"type": "chunk",    "text": "def hello_world():"}
      data: {"type": "done",     "model": "...", "task_type": "coding",
                                 "tokens": 312, "elapsed": 4.2}
    """

    async def event_stream():
        routing_sent = False
        model_name   = ""
        task_type    = ""
        final_tokens = 0
        t_start      = time.time()

        async for chunk, model, ttype, tokens, done in route_task(
            req.message,
            project_context=req.context or "",
            force_model=req.force_model,
        ):
            # First non-sentinel iteration — announce routing decision
            if not routing_sent:
                model_name   = model
                task_type    = ttype
                routing_sent = True
                yield (
                    "data: "
                    + json.dumps({"type": "routing", "model": model, "task_type": ttype})
                    + "\n\n"
                )

            if done:
                final_tokens = tokens
                break

            if chunk:
                yield "data: " + json.dumps({"type": "chunk", "text": chunk}) + "\n\n"

        elapsed = round(time.time() - t_start, 2)
        yield (
            "data: "
            + json.dumps({
                "type":      "done",
                "model":     model_name,
                "task_type": task_type,
                "tokens":    final_tokens,
                "elapsed":   elapsed,
            })
            + "\n\n"
        )

        # Persist call stats
        try:
            _history.log_model_call(
                model=model_name,
                task_type=task_type,
                tokens=final_tokens,
            )
        except Exception:
            pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
