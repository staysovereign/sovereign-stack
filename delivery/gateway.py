from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

log = logging.getLogger("sovereign.delivery")

DUMB_PHONE = os.environ.get("DUMB_PHONE_NUMBER", "")


@dataclass
class SendResult:
    success: bool
    gateway: str
    error: str | None = None


async def send(sms_body: str) -> SendResult:
    """
    Send an SMS to the dumb phone.
    Tries Twilio if configured, falls back to gammu if configured,
    otherwise logs a warning (useful during local development).
    """
    if not DUMB_PHONE:
        log.warning("DUMB_PHONE_NUMBER not set — SMS not sent: %s", sms_body)
        return SendResult(success=False, gateway="none", error="DUMB_PHONE_NUMBER not configured")

    if _twilio_configured():
        return await _send_twilio(sms_body)

    if _gammu_configured():
        return await _send_gammu(sms_body)

    log.warning("No SMS gateway configured — message not sent: %s", sms_body)
    return SendResult(success=False, gateway="none", error="No gateway configured")


# ── Twilio ─────────────────────────────────────────────────────────────────────

def _twilio_configured() -> bool:
    return bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"))


async def _send_twilio(body: str) -> SendResult:
    try:
        from twilio.rest import Client as TwilioClient
    except ImportError:
        return SendResult(success=False, gateway="twilio", error="twilio package not installed")

    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")

    def _call() -> str:
        client = TwilioClient(account_sid, auth_token)
        msg = client.messages.create(body=body, from_=from_number, to=DUMB_PHONE)
        return msg.sid

    try:
        sid = await asyncio.to_thread(_call)
        log.info("SMS sent via Twilio sid=%s", sid)
        return SendResult(success=True, gateway="twilio")
    except Exception as exc:
        log.error("Twilio send failed: %s", exc)
        return SendResult(success=False, gateway="twilio", error=str(exc))


# ── Gammu (USB GSM modem) ──────────────────────────────────────────────────────

def _gammu_configured() -> bool:
    return bool(os.environ.get("GAMMU_CONFIG_PATH"))


async def _send_gammu(body: str) -> SendResult:
    """
    Full sovereignty path: send via a USB GSM modem through python-gammu.
    Requires gammu installed in the container and GAMMU_CONFIG_PATH set.

    To enable:
      1. Attach a USB GSM modem to the host
      2. Install gammu: apt-get install gammu python3-gammu
      3. Write a gammu config file (see gammu --help)
      4. Set GAMMU_CONFIG_PATH=/etc/gammu-smsdrc in .env
    """
    try:
        import gammu  # type: ignore
    except ImportError:
        return SendResult(success=False, gateway="gammu", error="python-gammu not installed")

    config_path = os.environ["GAMMU_CONFIG_PATH"]

    def _call() -> None:
        sm = gammu.StateMachine()
        sm.ReadConfig(Filename=config_path)
        sm.Init()
        sm.SendSMS({
            "Text": body,
            "SMSC": {"Location": 1},
            "Number": DUMB_PHONE,
        })

    try:
        await asyncio.to_thread(_call)
        log.info("SMS sent via gammu to %s", DUMB_PHONE)
        return SendResult(success=True, gateway="gammu")
    except Exception as exc:
        log.error("Gammu send failed: %s", exc)
        return SendResult(success=False, gateway="gammu", error=str(exc))
