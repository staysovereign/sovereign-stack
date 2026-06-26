/**
 * SMS connector — Twilio inbound webhook.
 *
 * Twilio calls this endpoint when an SMS arrives at your Twilio number.
 * Configure the webhook URL in Twilio console:
 *   https://console.twilio.com → Phone Numbers → your number → Messaging
 *   → Webhook: POST https://your-sovereign-host/sms/webhook
 *
 * Two paths:
 *   From == DUMB_PHONE_NUMBER → POST /reply  (dumb phone reply command)
 *   From == anyone else       → POST /ingest  (urgency engine)
 */

const express = require('express');
const twilio = require('twilio');
const { dispatch, buildMessage } = require('../shared/normalize');

const router = express.Router();
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN;
const DUMB_PHONE = (process.env.DUMB_PHONE_NUMBER || '').trim();
const CORE_BASE = (process.env.CORE_INGEST_URL || 'http://core:8000/ingest').replace('/ingest', '');

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

router.post('/webhook', express.urlencoded({ extended: false }), async (req, res) => {
  if (TWILIO_AUTH_TOKEN && process.env.NODE_ENV === 'production') {
    const signature = req.headers['x-twilio-signature'];
    const url = process.env.TWILIO_WEBHOOK_URL;
    const valid = twilio.validateRequest(TWILIO_AUTH_TOKEN, signature, url, req.body);
    if (!valid) {
      return res.status(403).send('<Response></Response>');
    }
  }

  const { From, Body, MessageSid, NumMedia } = req.body;

  // Dumb phone reply — route to reply router, not urgency engine
  if (DUMB_PHONE && From === DUMB_PHONE) {
    try {
      await forwardToReply(From, Body || '');
    } catch (err) {
      console.error('[sms] reply forward failed:', err.message);
    }
    return res.type('text/xml').send('<Response></Response>');
  }

  // Regular inbound SMS from a contact → urgency engine
  const normalized = buildMessage({
    platform: 'sms',
    sender: {
      id: From,
      name: null,
      phone: From,
    },
    content: {
      type: 'text',
      body: Body || '',
    },
    group: null,
    metadata: {
      message_sid: MessageSid,
      num_media: parseInt(NumMedia || '0', 10),
      to: req.body.To,
    },
  });

  try {
    await dispatch(normalized);
    res.type('text/xml').send('<Response></Response>');
  } catch (err) {
    console.error('[sms] dispatch failed:', err.message);
    res.type('text/xml').send('<Response></Response>');
  }
});

console.log('[sms] connector mounted at /sms/webhook');

module.exports = router;
