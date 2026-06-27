/**
 * InfiniReach inbound webhook.
 *
 * InfiniReach (https://infinireach.io) calls this endpoint when your Android's
 * SIM receives an SMS. Configure it in the InfiniReach dashboard:
 *   Webhook URL: POST https://<your-public-sovereign-host>/infinireach/webhook
 *   Event:       message.inbound
 *
 * Payload (message.inbound):
 *   { "event": "message.inbound",
 *     "data": { "from": "+57...", "to": "+57...", "body": "...", ... } }
 *
 * Routing mirrors the SMS connector:
 *   data.from == DUMB_PHONE_NUMBER → POST /reply  (your dumb-phone reply command)
 *   data.from == anyone else       → POST /ingest (urgency engine, as an SMS)
 *
 * Note: because InfiniReach is a cloud relay, it must reach this endpoint over
 * the internet — expose the connectors port publicly (port-forward or a tunnel
 * such as ngrok/cloudflared). Optionally set INFINIREACH_WEBHOOK_SECRET and add
 * ?secret=... to the webhook URL to reject unauthenticated calls.
 */

const express = require('express');
const { dispatch, buildMessage, samePhone } = require('../shared/normalize');

const router = express.Router();
const DUMB_PHONE = (process.env.DUMB_PHONE_NUMBER || '').trim();
const CORE_BASE = (process.env.CORE_INGEST_URL || 'http://core:8000/ingest').replace('/ingest', '');
const WEBHOOK_SECRET = process.env.INFINIREACH_WEBHOOK_SECRET || '';

async function forwardToReply(fromNumber, body) {
  const fetch = (await import('node-fetch')).default;
  const res = await fetch(`${CORE_BASE}/reply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_number: fromNumber, body }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Core /reply rejected [${res.status}]: ${text}`);
  }
}

router.post('/webhook', express.json(), async (req, res) => {
  if (WEBHOOK_SECRET && req.query.secret !== WEBHOOK_SECRET) {
    return res.status(403).json({ error: 'invalid secret' });
  }

  const event = req.body?.event;
  const data = req.body?.data || {};

  // Only inbound messages matter; ack everything else (e.g. delivery receipts).
  if (event !== 'message.inbound') {
    return res.json({ ok: true, ignored: event || 'unknown' });
  }

  const from = (data.from || '').trim();
  const body = data.body || '';

  if (!from) {
    return res.status(400).json({ error: 'missing data.from' });
  }

  // Dumb-phone reply → route to the reply handler, not the urgency engine.
  // InfiniReach reports `from` in national format, so match loosely but forward
  // the canonical DUMB_PHONE so the core /reply check (strict equality) passes.
  if (DUMB_PHONE && samePhone(from, DUMB_PHONE)) {
    try {
      await forwardToReply(DUMB_PHONE, body);
    } catch (err) {
      console.error('[infinireach] reply forward failed:', err.message);
    }
    return res.json({ ok: true, routed: 'reply' });
  }

  // Inbound SMS from a contact → urgency engine.
  const normalized = buildMessage({
    platform: 'sms',
    sender: { id: from, name: null, phone: from },
    content: { type: 'text', body },
    group: null,
    metadata: {
      message_id: data.messageId || null,
      device_id: data.deviceId || null,
      to: data.to || null,
      source: 'infinireach',
    },
  });

  try {
    await dispatch(normalized);
  } catch (err) {
    console.error('[infinireach] dispatch failed:', err.message);
  }
  return res.json({ ok: true, routed: 'ingest' });
});

console.log('[infinireach] inbound webhook mounted at /infinireach/webhook');

module.exports = router;
