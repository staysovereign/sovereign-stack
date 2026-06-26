from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Platform(str, Enum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class ContentType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    STICKER = "sticker"


class Sender(BaseModel):
    id: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class Content(BaseModel):
    type: ContentType
    body: str | None = None
    # For media: URL to the file as stored by the connector
    media_url: str | None = None
    # Duration in seconds for voice notes
    duration_seconds: int | None = None


class NormalizedMessage(BaseModel):
    id: UUID
    timestamp: str  # ISO8601
    platform: Platform
    sender: Sender
    content: Content
    # None for direct messages, group id for group messages
    group: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
