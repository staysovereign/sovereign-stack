from __future__ import annotations

import logging
import os

import anthropic

log = logging.getLogger("sovereign.reply.claude")

MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")


async def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def generate(prompt: str) -> str | None:
    """
    Send a prompt to the Claude API, with web search enabled, for questions
    that need live/current information the local Ollama model can't have.
    Returns None if ANTHROPIC_API_KEY isn't set or the request fails.

    Unlike advisor.ollama.generate() (the sovereign default), this leaves the
    machine and goes to Anthropic's cloud. Only call it for a direct,
    user-initiated "ask the world" request — never with ambient conversation
    content the user hasn't chosen to send.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=MODEL,
            max_tokens=512,
            output_config={"effort": "low"},
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 1}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return text or None
    except Exception as exc:
        log.warning("Claude unavailable: %s", exc)
        return None
