from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CouncilMember:
    platform: str         # 'telegram', 'whatsapp', 'email', 'sms'
    sender_id: str        # platform-specific identifier
    name: str             # display name in Sovereign
    quiet_hours_override: bool = False  # reaches you even during quiet hours
    id: int | None = None
    created_at: str | None = None
