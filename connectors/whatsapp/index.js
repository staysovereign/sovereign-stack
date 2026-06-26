/**
 * WhatsApp connector — mautrix-whatsapp webhook receiver.
 *
 * mautrix-whatsapp runs as a Matrix Application Service bridge.
 * This connector receives Matrix events from the bridge via a webhook
 * and normalizes them into Sovereign's message format.
 *
 * Setup required:
 *   1. Run mautrix-whatsapp as a Docker service (see docker-compose.yml)
 *   2. Register the bridge with a Matrix homeserver (Synapse)
 *   3. Set WHATSAPP_BRIDGE_SECRET in .env to validate webhook signatures
 *
 * See: https://docs.mau.fi/bridges/go/whatsapp/index.html
 */

const express = require('express');
const crypto = require('crypto');
const { dispatch, buildMessage } = require('../shared/normalize');

const router = express.Router();
const BRIDGE_SECRET = process.env.WHATSAPP_BRIDGE_SECRET;

function verifySignature(req) {
  if (!BRIDGE_SECRET) return true; // dev mode — skip verification
  const sig = req.headers['x-mautrix-signature'];
  if (!sig) return false;
  const expected = crypto
    .createHmac('sha256', BRIDGE_SECRET)
    .update(JSON.stringify(req.body))
    .digest('hex');
  return sig === expected;
}

function contentFromMatrixEvent(event) {
  const msgtype = event.content?.msgtype;
  if (msgtype === 'm.text') return { type: 'text', body: event.content.body };
  if (msgtype === 'm.audio') return { type: 'voice', media_url: event.content.url, duration_seconds: event.content.info?.duration };
  if (msgtype === 'm.image') return { type: 'image', media_url: event.content.url };
  if (msgtype === 'm.video') return { type: 'video', media_url: event.content.url };
  if (msgtype === 'm.file') return { type: 'document', media_url: event.content.url };
  return { type: 'text', body: event.content?.body || '[unsupported]' };
}

router.post('/webhook', express.json(), async (req, res) => {
  if (!verifySignature(req)) {
    return res.status(401).json({ error: 'invalid signature' });
  }

  const event = req.body;

  // Only process incoming messages (not bridge control events or our own messages)
  if (event.type !== 'm.room.message' || event.sender?.endsWith(':sovereign')) {
    return res.status(200).json({ status: 'ignored' });
  }

  const roomId = event.room_id;
  // mautrix encodes phone numbers in the sender MXID: @whatsapp_[phone]:[homeserver]
  const phoneMatch = event.sender?.match(/@whatsapp_(\d+):/);
  const phone = phoneMatch ? `+${phoneMatch[1]}` : null;

  const normalized = buildMessage({
    platform: 'whatsapp',
    sender: {
      id: event.sender,
      name: event.content?.['m.relates_to']?.display_name || null,
      phone,
    },
    content: contentFromMatrixEvent(event),
    // Group rooms have multiple participants; DM rooms are 1:1
    group: event.content?.['m.room.member']?.membership ? roomId : null,
    metadata: {
      room_id: roomId,
      event_id: event.event_id,
      origin_server_ts: event.origin_server_ts,
    },
  });

  try {
    await dispatch(normalized);
    res.status(202).json({ status: 'accepted' });
  } catch (err) {
    console.error('[whatsapp] dispatch failed:', err.message);
    res.status(500).json({ error: 'dispatch failed' });
  }
});

console.log('[whatsapp] connector mounted at /whatsapp/webhook');

module.exports = router;
