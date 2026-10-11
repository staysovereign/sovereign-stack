from __future__ import annotations

import unicodedata

# Symbols an LLM commonly writes that aren't in the GSM-7 SMS alphabet and
# don't decompose via Unicode normalization (e.g. "°" has no accent to strip).
# Anything outside GSM-7 forces the whole message into UCS-2 encoding, which
# only fits ~70 chars per segment instead of ~160 — if the gateway/carrier
# doesn't concatenate multi-part SMS cleanly, the message arrives truncated
# at that boundary instead of failing loudly.
_REPLACEMENTS = {
    "°": "",
    "—": "-",
    "–": "-",
    "…": "...",
    "•": "-",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
}


def sanitize_for_sms(text: str) -> str:
    """
    Make text safe for single-segment GSM-7 SMS: replace common non-GSM-7
    symbols, strip accents (café -> cafe), then drop anything still non-ASCII
    (emoji, etc.) rather than risk forcing UCS-2 encoding.
    """
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.encode("ascii", "ignore").decode("ascii")
