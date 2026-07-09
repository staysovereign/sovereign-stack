require('dotenv').config();

const fs = require('fs');
const express = require('express');

const app = express();
const PORT = process.env.CONNECTORS_PORT || 3000;

// Webhook-based connectors mount as Express routers
app.use('/sms', require('./sms/index'));
app.use('/infinireach', require('./infinireach/index'));
app.use('/android', require('./android/index'));

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.listen(PORT, () => {
  console.log(`[connectors] webhook server listening on :${PORT}`);
});

// Optional HTTPS listener for the capcom6 inbound webhook. capcom6 only posts to
// https:// (or 127.0.0.1) URLs, so we serve the same app over TLS when a cert is
// present. Use a cert issued by capcom6's CA for this host's LAN IP (its root is
// embedded in the app, so nothing needs installing on the phone). No cert → no
// HTTPS listener, no error — everything else runs as normal.
const TLS_CERT = process.env.WEBHOOK_TLS_CERT || '/certs/webhook.crt';
const TLS_KEY = process.env.WEBHOOK_TLS_KEY || '/certs/webhook.key';
const TLS_PORT = process.env.CONNECTORS_TLS_PORT || 3443;
if (fs.existsSync(TLS_CERT) && fs.existsSync(TLS_KEY)) {
  try {
    require('https')
      .createServer({ cert: fs.readFileSync(TLS_CERT), key: fs.readFileSync(TLS_KEY) }, app)
      .listen(TLS_PORT, () => console.log(`[connectors] HTTPS webhook server listening on :${TLS_PORT}`));
  } catch (err) {
    console.error('[connectors] HTTPS listener failed to start:', err.message);
  }
} else {
  console.log('[connectors] no webhook TLS cert found — HTTPS webhook listener disabled');
}

// Polling-based connectors start their own loops
if (process.env.TELEGRAM_BOT_TOKEN) {
  require('./telegram/index');
} else {
  console.warn('[telegram] TELEGRAM_BOT_TOKEN not set — connector skipped');
}

if (process.env.EMAIL_IMAP_HOST) {
  require('./email/index');
} else {
  console.warn('[email] EMAIL_IMAP_HOST not set — connector skipped');
}

// WhatsApp via the mautrix Matrix bridge — runs a Matrix /sync loop, not a webhook
if (process.env.MATRIX_ACCESS_TOKEN) {
  require('./whatsapp/index');
} else {
  console.warn('[whatsapp] MATRIX_ACCESS_TOKEN not set — connector skipped');
}
