from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class CommandType(str, Enum):
    REPLY_LATEST = "reply_latest"    # r [text]  — reply to most recent session
    REPLY_NAME   = "reply_name"      # r name [text]  — reply to contact by name
    REPLY_INDEX  = "reply_index"     # r N [text]  — reply to Nth recent message
    LIST         = "list"            # list
    READ         = "read"            # read N
    STATUS       = "status"          # status


@dataclass
class ParsedCommand:
    type: CommandType
    text: str | None = None    # reply body
    name: str | None = None    # for REPLY_NAME
    index: int | None = None   # for REPLY_INDEX / READ


def parse(raw: str) -> ParsedCommand:
    s = raw.strip()

    if s.lower() == "status":
        return ParsedCommand(type=CommandType.STATUS)

    if s.lower() == "list":
        return ParsedCommand(type=CommandType.LIST)

    # read N
    m = re.match(r"^read\s+(\d+)$", s, re.IGNORECASE)
    if m:
        return ParsedCommand(type=CommandType.READ, index=int(m.group(1)))

    # r N [text]
    m = re.match(r"^r\s+(\d+)\s+(.+)$", s, re.IGNORECASE)
    if m:
        return ParsedCommand(type=CommandType.REPLY_INDEX, index=int(m.group(1)), text=m.group(2))

    # r name [text]  — name is a single word that is NOT a number
    m = re.match(r"^r\s+([A-Za-z]\w*)\s+(.+)$", s, re.IGNORECASE)
    if m:
        return ParsedCommand(type=CommandType.REPLY_NAME, name=m.group(1).lower(), text=m.group(2))

    # r [text]
    m = re.match(r"^r\s+(.+)$", s, re.IGNORECASE)
    if m:
        return ParsedCommand(type=CommandType.REPLY_LATEST, text=m.group(1))

    # Bare text with no prefix → treat as reply to most recent active session
    return ParsedCommand(type=CommandType.REPLY_LATEST, text=s)
