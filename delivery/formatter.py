from __future__ import annotations

from core.models.message import ContentType, NormalizedMessage, Platform
from engine.result import EngineResult, Tier

_TAGS: dict[str, str] = {
    Platform.WHATSAPP.value:  "WA",
    Platform.TELEGRAM.value:  "TG",
    Platform.EMAIL.value:     "EM",
    Platform.SMS.value:       "SM",
    Platform.INSTAGRAM.value: "IG",
    Platform.FACEBOOK.value:  "FB",
}

# Total SMS budget: 160 GSM-7 chars.
# We reserve up to ~20 chars for the "[XX] Name: " prefix,
# leaving 140 for the body — matches the spec exactly.
_BODY_LIMIT = 140


def format_sms(
    message: NormalizedMessage,
    result: EngineResult,
    council_name: str | None,
) -> str:
    tag = _TAGS.get(message.platform.value, message.platform.value[:2].upper())
    name = council_name or message.sender.name or message.sender.id[:12]

    body = _build_body(message, result)
    prefix = f"[{tag}] {name}: "

    # Truncate body so the full SMS fits in 160 chars
    available = 160 - len(prefix)
    if len(body) > available:
        body = body[: available - 1] + "…"

    return prefix + body


def _build_body(message: NormalizedMessage, result: EngineResult) -> str:
    content = message.content

    # Frequency escalation — show the signal, not the content
    if result.tier == Tier.DECREE and result.decree_name == "Frequency escalation":
        from core.db import sender_timestamps
        from datetime import datetime, timezone

        key = f"{message.platform.value}:{message.sender.id}"
        now = datetime.now(timezone.utc)
        window = 600  # matches the default decree; good enough for display
        recent = [ts for ts in sender_timestamps[key] if (now - ts).total_seconds() <= window]
        count = len(recent)
        minutes = window // 60
        return f"⚡ {count} messages in {minutes} min"

    # Voice note
    if content.type == ContentType.VOICE:
        duration = f" ({content.duration_seconds}s)" if content.duration_seconds else ""
        tier_label = _tier_label(result)
        return f"\U0001f3a4 Voice note{duration} · {tier_label}"

    # Image / video / document
    if content.type == ContentType.IMAGE:
        return "\U0001f4f7 Image"
    if content.type == ContentType.VIDEO:
        return "\U0001f4f9 Video"
    if content.type == ContentType.DOCUMENT:
        return "\U0001f4ce Document"

    # Plain text — truncate to body limit
    body = content.body or ""
    if len(body) > _BODY_LIMIT:
        return body[: _BODY_LIMIT - 1] + "…"
    return body


def _tier_label(result: EngineResult) -> str:
    if result.tier == Tier.COUNCIL:
        return "Council"
    if result.tier == Tier.DECREE:
        return result.decree_name or "Decree"
    if result.tier == Tier.ADVISOR:
        return "Advisor"
    return "Sovereign"
