/**
 * Android local gateway — inbound webhook.
 *
 * Companion to delivery/gateway.py's `android` outbound path. The on-phone SMS
 * gateway app sends Sovereign's urgent texts from its SIM; when that SIM later
 * *receives* an SMS (your reply from the dumb phone, or a new inbound SMS), the
 * phone must forward it here so Sovereign can route the reply back to the
 * original chat (WhatsApp/Instagram/email/Telegram) — exactly like the Twilio
 * and InfiniReach connectors do.
 *
 * Some gateway apps can forward received SMS themselves; send-only apps (e.g.
 * "Simple SMS Gateway") can't, so pair them with a tiny incoming-SMS forwarder
 * app on the same phone. Either way, point the forwarder at:
 *
 *   POST http://<this-host-lan-ip>:4000/android/webhook
 *
 * Because the phone is on your LAN, no public URL/tunnel is needed.
 *
 * Field names differ between apps, so we accept the common shapes (and unwrap a
 * nested data/payload/message object first):
 *   from:  from | sender | phoneNumber | phone | number | address | originator
 *   body:  text | message | body | content | msg
 * Unrecognized payloads are logged raw (once) so the format can be added.
 *
 * Routing mirrors the other SMS connectors:
 *   from == DUMB_PHONE_NUMBER → POST /reply  (your dumb-phone reply command)
 *   from == anyone else       → POST /ingest (urgency engine, as an SMS)
 *
 * Optional: set ANDROID_SMS_GATEWAY_WEBHOOK_SECRET and append ?secret=... to the
 * webhook URL to reject unauthenticated calls.
 */

const express = require('express');
const { dispatch, buildMessage, samePhone } = require('../shared/normalize');

const router = express.Router();
const DUMB_PHONE = (process.env.DUMB_PHONE_NUMBER || '').trim();
const CORE_BASE = (process.env.CORE_INGEST_URL || 'http://core:8000/ingest').replace('/ingest', '');
const WEBHOOK_SECRET = process.env.ANDROID_SMS_GATEWAY_WEBHOOK_SECRET || '';

const FROM_KEYS = ['from', 'sender', 'phoneNumber', 'phone', 'number', 'address', 'originator'];
const BODY_KEYS = ['text', 'message', 'body', 'content', 'msg'];

function pick(obj, keys) {
  for (const k of keys) {
    if (obj && obj[k] != null && String(obj[k]).trim() !== '') return String(obj[k]).trim();
  }
  return '';
}

// Flatten one level of common wrapper objects so {payload:{phoneNumber,message}}
// (capcom6), {data:{from,body}}, etc. all resolve.
function flatten(body) {
  const merged = { ...body };
  for (const wrap of ['data', 'payload', 'message', 'sms']) {
    if (body[wrap] && typeof body[wrap] === 'object') Object.assign(merged, body[wrap]);
  }
  return merged;
}

async function forwardToReply(fromNumber, body) {
  const fetch = (await import('node-fetch')).default;
  const res = await fetch(`${CORE_BASE}/reply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_number: fromNumber, body }),
  });
  if (!res.ok) throw new Error(`Core /reply rejected [${res.status}]: ${await res.text()}`);
}

router.post('/webhook', express.json(), express.urlencoded({ extended: true }), async (req, res) => {
  if (WEBHOOK_SECRET && req.query.secret !== WEBHOOK_SECRET) {
    return res.status(403).json({ error: 'invalid secret' });
  }

  const raw = req.body || {};
  const src = flatten(raw);
  const from = pick(src, FROM_KEYS);
  const body = pick(src, BODY_KEYS);

  if (!from) {
    console.warn('[android] inbound webhook: no sender field found. Raw payload:', JSON.stringify(raw).slice(0, 400));
    return res.status(400).json({ error: 'missing sender field' });
  }

  // Dumb-phone reply → reply handler. Match loosely on trailing digits (apps
  // report national format), but forward the canonical DUMB_PHONE so core's
  // strict /reply equality check passes.
  if (DUMB_PHONE && samePhone(from, DUMB_PHONE)) {
    try {
      await forwardToReply(DUMB_PHONE, body);
      console.log('[android] dumb-phone reply forwarded to /reply');
    } catch (err) {
      console.error('[android] reply forward failed:', err.message);
    }
    return res.json({ ok: true, routed: 'reply' });
  }

  // Inbound SMS from a contact → urgency engine.
  const normalized = buildMessage({
    platform: 'sms',
    sender: { id: from, name: null, phone: from },
    content: { type: 'text', body },
    group: null,
    metadata: { source: 'android-gateway' },
  });
  try {
    await dispatch(normalized);
  } catch (err) {
    console.error('[android] dispatch failed:', err.message);
  }
  return res.json({ ok: true, routed: 'ingest' });
});

console.log('[android] inbound webhook mounted at /android/webhook');

module.exports = router;
