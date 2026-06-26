from __future__ import annotations

import json
import logging
import os

import httpx

log = logging.getLogger("sovereign.advisor.ollama")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")


async def available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            res = await client.get(f"{OLLAMA_URL}/api/tags")
            return res.status_code == 200
    except Exception:
        return False


async def generate(prompt: str) -> str | None:
    """
    Send a prompt to the local Ollama instance and return the response text.
    Returns None if Ollama is unreachable.

    Privacy contract: this function MUST only be called with anonymized,
    statistical summaries — never with message content, sender names,
    or any data that could identify a conversation.
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 400},
                },
            )
            res.raise_for_status()
            return res.json().get("response", "").strip()
    except Exception as exc:
        log.warning("Ollama unavailable: %s", exc)
        return None


async def suggest_decrees(stats: dict) -> list[dict]:
    """
    Ask Ollama to suggest Decree improvements based on anonymized behavioral stats.
    Returns a list of suggestion dicts, or [] if Ollama is unavailable.

    The stats dict contains ONLY aggregated, anonymous data:
    - per-platform accuracy rates
    - false positive / false negative counts
    - frequency patterns by hour of day
    No sender names, no message content, no identifiable information.
    """
    prompt = _build_prompt(stats)
    response = await generate(prompt)
    if not response:
        return []

    try:
        # Attempt to extract JSON from the response
        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    # If no valid JSON, return a raw text suggestion
    return [{"type": "pattern", "body": response[:300]}]


def _build_prompt(stats: dict) -> str:
    platforms = stats.get("platforms", {})
    platform_lines = "\n".join(
        f"  - {p}: {d['total']} signals, {d['urgency_rate']:.0%} urgency rate, "
        f"{d['false_positives']} false positives, {d['false_negatives']} false negatives"
        for p, d in platforms.items()
    )

    high_urgency_senders = stats.get("high_urgency_senders", 0)
    council_candidates = stats.get("council_candidates", 0)
    total_signals = stats.get("total_signals", 0)
    fp_rate = stats.get("overall_false_positive_rate", 0)
    fn_rate = stats.get("overall_false_negative_rate", 0)

    return f"""You are an assistant for a personal message urgency filter called Sovereign.
Your role is to suggest improvements to the user's filter rules based on anonymized behavioral data.

IMPORTANT: You have NO access to message content, sender names, or any identifiable information.
Work only from the statistical patterns below.

Behavioral summary ({total_signals} total signals):
{platform_lines}
- Senders with consistently high urgency rate (>80%): {high_urgency_senders}
- Senders who may qualify for VIP status (Council): {council_candidates}
- Overall false positive rate: {fp_rate:.0%}
- Overall false negative rate: {fn_rate:.0%}

Current filter rules in effect:
- Hold all group messages (always)
- Pass keywords: emergency, urgent, hospital, accident, llámame, ayuda, please call
- Pass frequency: same sender 3+ messages in 10 minutes

Based on this data, suggest 1-3 specific improvements to the filter rules.
Be concrete: either suggest adding/removing keywords, adjusting the frequency threshold,
or noting that some senders should be elevated to VIP status.

Respond ONLY with a JSON array. Each item must have:
  "type": "decree_suggestion" | "council_promotion" | "pattern"
  "body": one-sentence human-readable suggestion (no names, no content)
  "confidence": 0.0-1.0

Example: [{{"type": "decree_suggestion", "body": "Consider lowering the frequency threshold from 3 to 2 messages — your false negative rate suggests urgent senders are being held too long.", "confidence": 0.7}}]
"""
