/**
 * SMS connector — Twilio inbound webhook.
 *
 * Twilio calls this endpoint when an SMS arrives at your Twilio number.
 * Configure the webhook URL in Twilio console:
 *   https://console.twilio.com → Phone Numbers → your number → Messaging
 *   → Webhook: POST https://your-sovereign-host/sms/webhook
 *
 * For full-sovereignty (USB GSM modem via gammu), see:
 *   connectors/sms/gammu.js (added in a later iteration)
 */

const express = require('express');
const twilio = require('twilio');
const { dispatch, buildMessage } = require('../shared/normalize');

const router = express.Router();
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN;

router.post('/webhook', express.urlencoded({ extended: false }), async (req, res) => {
  // Validate Twilio signature in production
  if (TWILIO_AUTH_TOKEN && process.env.NODE_ENV === 'production') {
    const signature = req.headers['x-twilio-signature'];
    const url = process.env.TWILIO_WEBHOOK_URL;
    const valid = twilio.validateRequest(TWILIO_AUTH_TOKEN, signature, url, req.body);
    if (!valid) {
      return res.status(403).send('<Response></Response>');
    }
  }

  const { From, Body, MessageSid, NumMedia } = req.body;

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
    // Twilio expects TwiML in response — empty response means no auto-reply
    res.type('text/xml').send('<Response></Response>');
  } catch (err) {
    console.error('[sms] dispatch failed:', err.message);
    res.type('text/xml').send('<Response></Response>');
  }
});

console.log('[sms] connector mounted at /sms/webhook');

module.exports = router;
