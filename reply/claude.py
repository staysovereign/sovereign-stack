from __future__ import annotations

import logging
import os

import aiosqlite
import anthropic

from reply.actions import ACTION_HANDLERS, TOOLS as ACTION_TOOLS

log = logging.getLogger("sovereign.reply.claude")

MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")

MAX_TOOL_ROUNDS = 3


async def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def generate(
    prompt: str,
    *,
    history: list[dict] | None = None,
    db: aiosqlite.Connection | None = None,
) -> str | None:
    """
    Send a prompt to the Claude API, with web search enabled, for questions
    that need live/current information the local Ollama model can't have.
    Returns None if ANTHROPIC_API_KEY isn't set or the request fails.

    Unlike advisor.ollama.generate() (the sovereign default), this leaves the
    machine and goes to Anthropic's cloud. Only call it for a direct,
    user-initiated "ask the world" request — never with ambient conversation
    content the user hasn't chosen to send.

    `history` is prior (user, assistant) turns to prepend — e.g. for a
    follow-up SMS sent soon after the last one. `db` is required only if the
    model decides to call one of reply.actions' tools (set_reminder,
    add_to_council) — pass it whenever one might apply.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    messages = list(history or []) + [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 1}, *ACTION_TOOLS]

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = None

        for _ in range(MAX_TOOL_ROUNDS):
            response = await client.messages.create(
                model=MODEL,
                max_tokens=512,
                output_config={"effort": "low"},
                tools=tools,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                break

            tool_uses = [
                block for block in response.content
                if block.type == "tool_use" and block.name in ACTION_HANDLERS
            ]
            if not tool_uses or db is None:
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in tool_uses:
                try:
                    result_text = await ACTION_HANDLERS[block.name](block.input, db)
                except Exception as exc:
                    log.exception("Action %s failed", block.name)
                    result_text = f"Action failed: {exc}"
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
                )
            messages.append({"role": "user", "content": tool_results})

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return text or None
    except Exception as exc:
        log.warning("Claude unavailable: %s", exc)
        return None
