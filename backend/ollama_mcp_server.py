#!/usr/bin/env python3
"""
ollama_mcp_server.py
MCP server that exposes Qwen3-Coder (via Ollama) as tools for Claude Code.

Claude Code calls these tools for pure code-writing tasks, keeping
expensive Claude API tokens reserved for reasoning and domain judgment.

Tools exposed:
  write_code   — generate new code from a task description
  edit_code    — apply described changes to existing code
  explain_code — quick code explanation (Qwen3 is fast for this)

Transport: stdio (Claude Code spawns this as a subprocess)
"""

import asyncio
import httpx
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODEL = "qwen3-coder:30b"

SYSTEM_PROMPT = (
    "You are an expert Python and Swift developer working on VedicAlpha — "
    "an Indian stock and commodity prediction app that combines Vedic Jyotish "
    "astrology with technical analysis. "
    "Write clean, production-ready code following existing patterns. "
    "Output ONLY the code — no markdown fences, no prose unless explicitly asked. "
    "Use brief inline comments for non-obvious logic. Never leave TODO placeholders."
)

server = Server("ollama-qwen3-coder")


async def call_ollama(prompt: str, temperature: float = 0.15) -> str:
    """Send a prompt to Qwen3-Coder and return the full response."""
    full_response = []
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_URL}/api/generate",
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_ctx":     32768,
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
                    full_response.append(text)
                if chunk.get("done"):
                    break
    return "".join(full_response).strip()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="write_code",
            description=(
                "Generate new code using the local Qwen3-Coder model (free, no API cost). "
                "Use this for: writing new functions, classes, endpoints, Swift views, "
                "tests, or any boilerplate from a clear spec. "
                "Returns raw code ready to paste into a file."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "What to write — be specific about function signatures, "
                                       "return types, and patterns to follow.",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language: python, swift, json, bash, etc.",
                        "default": "python",
                    },
                    "context": {
                        "type": "string",
                        "description": "Relevant existing code or imports the generated code "
                                       "must be compatible with.",
                        "default": "",
                    },
                },
                "required": ["task"],
            },
        ),
        Tool(
            name="edit_code",
            description=(
                "Apply described changes to existing code using Qwen3-Coder (free, no API cost). "
                "Use this for: refactoring, renaming, adding parameters, fixing syntax errors, "
                "or any mechanical transformation of existing code."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "current_code": {
                        "type": "string",
                        "description": "The existing code to be modified.",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Precise description of what to change.",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language of the code.",
                        "default": "python",
                    },
                },
                "required": ["current_code", "instructions"],
            },
        ),
        Tool(
            name="explain_code",
            description=(
                "Get a quick explanation of a code snippet from Qwen3-Coder. "
                "Faster and free compared to Claude. Good for understanding "
                "unfamiliar functions before editing them."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The code to explain.",
                    },
                    "question": {
                        "type": "string",
                        "description": "Specific question about the code (optional).",
                        "default": "What does this code do?",
                    },
                },
                "required": ["code"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "write_code":
        task     = arguments["task"]
        language = arguments.get("language", "python")
        context  = arguments.get("context", "")

        prompt = f"Language: {language}\n\nTask: {task}"
        if context:
            prompt += f"\n\nExisting code / context to be compatible with:\n{context}"

        result = await call_ollama(prompt)
        return [TextContent(type="text", text=result)]

    elif name == "edit_code":
        current      = arguments["current_code"]
        instructions = arguments["instructions"]
        language     = arguments.get("language", "python")

        prompt = (
            f"Language: {language}\n\n"
            f"Apply this change to the code below: {instructions}\n\n"
            f"Current code:\n{current}\n\n"
            f"Output ONLY the complete modified code, nothing else."
        )
        result = await call_ollama(prompt)
        return [TextContent(type="text", text=result)]

    elif name == "explain_code":
        code     = arguments["code"]
        question = arguments.get("question", "What does this code do?")

        prompt = f"{question}\n\nCode:\n{code}"
        result = await call_ollama(prompt, temperature=0.3)
        return [TextContent(type="text", text=result)]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
