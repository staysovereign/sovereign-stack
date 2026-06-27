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
    Send an SMS to the dumb phone via the selected gateway.

    SMS_GATEWAY picks one explicitly: 'twilio', 'android', or 'gammu'.
    If it's unset, the first *configured* gateway is used, in the order
    twilio → android → gammu. If none is configured the message is logged
    (useful during local development).
    """
    if not DUMB_PHONE:
        log.warning("DUMB_PHONE_NUMBER not set — SMS not sent: %s", sms_body)
        return SendResult(success=False, gateway="none", error="DUMB_PHONE_NUMBER not configured")

    gateways = {
        "twilio":      (_twilio_configured,      _send_twilio),
        "infinireach": (_infinireach_configured, _send_infinireach),
        "android":     (_android_configured,     _send_android),
        "gammu":       (_gammu_configured,       _send_gammu),
    }

    choice = os.environ.get("SMS_GATEWAY", "").strip().lower()
    if choice:
        if choice not in gateways:
            log.error("Unknown SMS_GATEWAY '%s' (expected: twilio, infinireach, android, gammu)", choice)
            return SendResult(success=False, gateway="none", error=f"Unknown SMS_GATEWAY '{choice}'")
        is_configured, sender = gateways[choice]
        if not is_configured():
            log.warning("SMS_GATEWAY=%s but it isn't configured — SMS not sent: %s", choice, sms_body)
            return SendResult(success=False, gateway=choice, error=f"{choice} selected but not configured")
        return await sender(sms_body)

    # Auto-detect: first configured gateway wins.
    for name in ("twilio", "infinireach", "android", "gammu"):
        is_configured, sender = gateways[name]
        if is_configured():
            return await sender(sms_body)

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


# ── InfiniReach (cloud relay that sends via your Android phone's SIM) ────────────
# https://infinireach.io — an Android app + cloud API. You POST to their API and
# your own phone sends the SMS from its SIM, so it's local-to-local (not subject
# to foreign A2P filtering). Good free-tier option when a USB GSM modem isn't
# available. To enable: set INFINIREACH_API_KEY and SMS_GATEWAY=infinireach.

INFINIREACH_DEFAULT_URL = "https://api.infinireach.io/api/v1/messages"


def _infinireach_configured() -> bool:
    return bool(os.environ.get("INFINIREACH_API_KEY"))


async def _send_infinireach(body: str) -> SendResult:
    import httpx

    api_key = os.environ["INFINIREACH_API_KEY"]
    url = os.environ.get("INFINIREACH_API_URL", INFINIREACH_DEFAULT_URL)
    payload = {"to": DUMB_PHONE, "message": body, "channel": "sms"}
    from_number = os.environ.get("INFINIREACH_FROM")
    if from_number:
        payload["from"] = from_number
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except Exception as exc:
        log.error("InfiniReach send failed: %s", exc)
        return SendResult(success=False, gateway="infinireach", error=str(exc))

    data = {}
    try:
        data = resp.json()
    except Exception:
        pass

    # Their API returns 2xx with {"success": true, "queued": true, "messageId": …}
    if resp.is_success and data.get("success") is not False:
        log.info("SMS sent via InfiniReach messageId=%s", data.get("messageId"))
        return SendResult(success=True, gateway="infinireach")

    detail = data.get("error") or data.get("message") or resp.text[:200]
    log.error("InfiniReach send failed: HTTP %s %s", resp.status_code, detail)
    return SendResult(success=False, gateway="infinireach", error=f"HTTP {resp.status_code}: {detail}")


# ── Android phone as SMS gateway (HTTP) ─────────────────────────────────────────
# For people who can't easily get a USB GSM modem: run an on-phone HTTP SMS
# gateway app (e.g. the open-source "SMS Gateway for Android",
# capcom6/android-sms-gateway) in *local server* mode. The phone sends via its
# own SIM — perfect where carriers block foreign A2P routes — and Sovereign
# reaches it over your LAN. No public URL or tunnel needed.
#
# To enable:
#   1. Install the app on a phone with a working SIM; enable Local server mode.
#   2. Put the phone on the same network as this host.
#   3. Set ANDROID_SMS_GATEWAY_URL (e.g. http://192.168.1.50:8080) and, if the
#      app requires auth, ANDROID_SMS_GATEWAY_USER / ANDROID_SMS_GATEWAY_PASS.
#   4. Set SMS_GATEWAY=android (or leave it to auto-detection).

def _android_configured() -> bool:
    return bool(os.environ.get("ANDROID_SMS_GATEWAY_URL"))


async def _send_android(body: str) -> SendResult:
    import httpx

    base = os.environ["ANDROID_SMS_GATEWAY_URL"].rstrip("/")
    user = os.environ.get("ANDROID_SMS_GATEWAY_USER", "")
    password = os.environ.get("ANDROID_SMS_GATEWAY_PASS", "")
    url = f"{base}/message"
    payload = {"message": body, "phoneNumbers": [DUMB_PHONE]}
    auth = (user, password) if (user or password) else None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, auth=auth)
    except Exception as exc:
        log.error("Android gateway send failed: %s", exc)
        return SendResult(success=False, gateway="android", error=str(exc))

    if resp.is_success:
        log.info("SMS sent via Android gateway (HTTP %s)", resp.status_code)
        return SendResult(success=True, gateway="android")

    detail = resp.text[:200]
    log.error("Android gateway send failed: HTTP %s %s", resp.status_code, detail)
    return SendResult(success=False, gateway="android", error=f"HTTP {resp.status_code}: {detail}")


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
