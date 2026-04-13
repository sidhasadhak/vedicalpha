"""
model_router.py
Routes tasks between Claude API (reasoning/research) and
Qwen3-Coder via Ollama (coding/file updates).

Claude handles:
  - Jyotish rule interpretation from PDFs
  - Prediction logic reasoning and debugging complex errors
  - Backtesting analysis and insights
  - Architecture decisions and domain knowledge
  - Web research tasks

Qwen3-Coder (qwen3-coder:30b via Ollama) handles:
  - Writing new Swift/Python files from a clear spec
  - Updating existing files with described changes
  - Adding boilerplate (new endpoints, new models, new routes)
  - Reformatting or restructuring code
  - Writing tests from a spec
  - Simple bug fixes (syntax, type errors)
  - Adding docstrings and comments
"""

import httpx
import json
import re
import os
from enum import Enum

OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODEL = "qwen3-coder:30b"   # 18 GB — best available on this machine

CLAUDE_SONNET = "claude-sonnet-4-6"
CLAUDE_OPUS   = "claude-opus-4-6"


class TaskType(Enum):
    REASONING   = "reasoning"    # → Claude
    RESEARCH    = "research"     # → Claude
    CODING      = "coding"       # → Qwen3/Ollama
    FILE_UPDATE = "file_update"  # → Qwen3/Ollama
    MIXED       = "mixed"        # → Claude (safe default)


# Keywords that push toward a coding/generation task
CODING_SIGNALS = [
    "write a", "create a file", "add a function", "update the file",
    "add endpoint", "add a route", "implement", "refactor",
    "add import", "fix the syntax", "add docstring", "write test",
    "create class", "add method", "update swift", "edit the",
    "rename", "move", "delete the function", "add parameter",
    "change the return type", "add error handling", "add logging",
    "write the code", "code for", "generate", "boilerplate",
    "create the", "write me", "build a", "make a function",
]

# Keywords that push toward a reasoning/research task
REASONING_SIGNALS = [
    "why", "explain", "analyse", "what does this mean",
    "interpret", "jyotish", "astrolog", "backtest result",
    "which rules", "should i", "what's the best approach",
    "research", "find information", "web search", "look up",
    "debug", "something is wrong", "not working correctly",
    "predict", "what signal", "confidence", "accuracy",
    "what is", "how does", "what's the difference",
    "what are", "tell me about", "review", "analyse the",
]

# These escalate to Claude Opus
OPUS_SIGNALS = [
    "interpret all rules from", "analyse the entire",
    "complex prediction", "why is accuracy low",
    "deep analysis", "compare all six books",
    "architectural decision", "fundamental problem",
    "interpret the entire", "comprehensive analysis",
    "analyse all six", "full review of",
]


def classify_task(message: str) -> TaskType:
    """Classify a task message to determine which model should handle it."""
    msg_lower = message.lower()

    coding_score    = sum(1 for s in CODING_SIGNALS    if s in msg_lower)
    reasoning_score = sum(1 for s in REASONING_SIGNALS if s in msg_lower)

    # File path in message → coding task
    if re.search(r'\b\w+\.(py|swift|json|md|txt|sh)\b', message):
        coding_score += 2

    # Code block markers → coding task
    if '```' in message or 'def ' in message or 'func ' in message:
        coding_score += 2

    # Explicit "make/build/create" → coding
    if re.search(r'\b(make|build|create|generate|produce)\s+(it|this|the|a)\b', msg_lower):
        coding_score += 1

    if reasoning_score > coding_score:
        return TaskType.REASONING
    elif coding_score > reasoning_score:
        return TaskType.CODING
    else:
        return TaskType.MIXED  # Claude when uncertain


def should_escalate_to_opus(message: str) -> bool:
    return any(s in message.lower() for s in OPUS_SIGNALS)


def get_claude_model(message: str) -> str:
    return CLAUDE_OPUS if should_escalate_to_opus(message) else CLAUDE_SONNET


async def run_ollama(prompt: str, context: str = ""):
    """
    Stream a coding task through Qwen3-Coder:30b via Ollama.
    Yields (text_chunk: str, tokens: int).
    Last yield is ("", final_token_count) to signal completion.
    """
    system = (
        "You are an expert Python and Swift developer working on VedicAlpha — "
        "a Vedic astrology Indian market prediction app. "
        "Write clean, production-ready code following existing patterns in the codebase. "
        "Output ONLY the code. No markdown fences unless showing a diff. "
        "Use brief inline comments for non-obvious logic. Never leave TODO placeholders."
    )
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    tokens = 0

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  OLLAMA_MODEL,
                "prompt": full_prompt,
                "system": system,
                "stream": True,
                "options": {
                    "temperature": 0.15,   # low for deterministic code
                    "num_ctx":     32768,  # large context for full file edits
                },
            },
        ) as resp:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = chunk.get("response", "")
                if text:
                    tokens += 1
                    yield text, tokens
                if chunk.get("done"):
                    # Final chunk has eval_count (total tokens generated)
                    tokens = chunk.get("eval_count", tokens)
                    yield "", tokens   # sentinel — done
                    break


async def run_claude_api(prompt: str, context: str = "", model: str = CLAUDE_SONNET):
    """
    Stream a reasoning/research task through the Claude API.
    Yields (text_chunk: str, tokens: int).
    Last yield is ("", final_token_count) to signal completion.
    Requires ANTHROPIC_API_KEY in environment.
    """
    try:
        import anthropic
    except ImportError:
        yield "[anthropic package not installed — run: pip install anthropic]", 0
        yield "", 0
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        yield "[ANTHROPIC_API_KEY not set — add it to .env then restart the server]", 0
        yield "", 0
        return

    client = anthropic.Anthropic(api_key=api_key)
    system = (
        "You are an expert in Vedic astrology (Jyotish), Indian financial markets, "
        "and software architecture. You are the reasoning engine for VedicAlpha — "
        "an Indian stock and commodity prediction app. "
        "Be precise. Cite the relevant Vedic text when interpreting astrological rules."
    )
    messages = []
    if context:
        messages.append({"role": "user",      "content": context})
        messages.append({"role": "assistant", "content": "Understood."})
    messages.append({"role": "user", "content": prompt})

    tokens = 0
    with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            tokens += 1
            yield text, tokens
        try:
            usage  = stream.get_final_message().usage
            tokens = usage.output_tokens
        except Exception:
            pass
    yield "", tokens   # sentinel — done


async def route_task(
    message: str,
    project_context: str = "",
    force_model: str = "auto",
):
    """
    Main routing entry point. Classifies the task and streams from
    the appropriate model.

    Yields: (chunk, model_name, task_type_str, tokens, is_done)
    """
    if force_model == "ollama":
        task_type = TaskType.CODING
    elif force_model == "claude":
        task_type = TaskType.REASONING
    else:
        task_type = classify_task(message)

    if task_type in (TaskType.CODING, TaskType.FILE_UPDATE):
        model_name = f"Qwen3-Coder ({OLLAMA_MODEL})"
        async for chunk, tokens in run_ollama(message, project_context):
            is_done = (chunk == "" and tokens > 0)
            yield chunk, model_name, task_type.value, tokens, is_done
    else:
        claude_model = get_claude_model(message)
        label        = "Claude Opus" if claude_model == CLAUDE_OPUS else "Claude Sonnet"
        model_name   = f"{label} ({claude_model})"
        async for chunk, tokens in run_claude_api(message, project_context, claude_model):
            is_done = (chunk == "" and tokens > 0)
            yield chunk, model_name, task_type.value, tokens, is_done
