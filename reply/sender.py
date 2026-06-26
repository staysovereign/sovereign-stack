from __future__ import annotations

import asyncio
import logging
import os
import uuid

import httpx

log = logging.getLogger("sovereign.reply")


async def send_reply(platform: str, chat_id: str, text: str) -> None:
    """
    Route a reply back to the originating platform.
    Raises on failure so the router can surface the error to the dumb phone.
    """
    if platform == "telegram":
        await _send_telegram(chat_id, text)
    elif platform == "whatsapp":
        await _send_whatsapp(chat_id, text)
    elif platform == "email":
        await _send_email(chat_id, text)
    elif platform == "sms":
        await _send_sms(chat_id, text)
    else:
        raise ValueError(f"No reply sender for platform: {platform}")


# ── Telegram ──────────────────────────────────────────────────────────────────

async def _send_telegram(chat_id: str, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        res.raise_for_status()
    log.info("[telegram] reply sent to chat_id=%s", chat_id)


# ── WhatsApp (mautrix Matrix room) ────────────────────────────────────────────

async def _send_whatsapp(room_id: str, text: str) -> None:
    """
    Send a message to a WhatsApp chat via the mautrix-whatsapp Matrix bridge.

    Requires:
      MATRIX_HOMESERVER_URL  — e.g. http://synapse:8008
      MATRIX_ACCESS_TOKEN    — bot/appservice token from mautrix registration
    """
    homeserver = os.environ.get("MATRIX_HOMESERVER_URL")
    token = os.environ.get("MATRIX_ACCESS_TOKEN")
    if not homeserver or not token:
        raise RuntimeError("MATRIX_HOMESERVER_URL / MATRIX_ACCESS_TOKEN not set")

    txn_id = str(uuid.uuid4()).replace("-", "")
    url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"

    async with httpx.AsyncClient() as client:
        res = await client.put(
            url,
            json={"msgtype": "m.text", "body": text},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        res.raise_for_status()
    log.info("[whatsapp] reply sent to room_id=%s", room_id)


# ── Email ─────────────────────────────────────────────────────────────────────

async def _send_email(to_email: str, text: str) -> None:
    try:
        import aiosmtplib  # type: ignore
        from email.message import EmailMessage
    except ImportError:
        raise RuntimeError("aiosmtplib not installed — run: pip install aiosmtplib")

    smtp_host = os.environ.get("EMAIL_SMTP_HOST") or os.environ.get("EMAIL_IMAP_HOST")
    smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    smtp_user = os.environ.get("EMAIL_SMTP_USER") or os.environ.get("EMAIL_IMAP_USER")
    smtp_pass = os.environ.get("EMAIL_SMTP_PASS") or os.environ.get("EMAIL_IMAP_PASS")

    if not smtp_host or not smtp_user or not smtp_pass:
        raise RuntimeError("Email SMTP credentials not set")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = "Re: (via Sovereign)"
    msg.set_content(text)

    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_pass,
        start_tls=True,
    )
    log.info("[email] reply sent to %s", to_email)


# ── SMS (external contact, not dumb phone) ────────────────────────────────────

async def _send_sms(to_phone: str, text: str) -> None:
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")

    if not account_sid or not auth_token or not from_number:
        raise RuntimeError("Twilio credentials not set")

    from twilio.rest import Client as TwilioClient

    def _call() -> None:
        client = TwilioClient(account_sid, auth_token)
        client.messages.create(body=text, from_=from_number, to=to_phone)

    await asyncio.to_thread(_call)
    log.info("[sms] reply sent to %s", to_phone)
