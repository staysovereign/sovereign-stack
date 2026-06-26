require('dotenv').config();

const express = require('express');

const app = express();
const PORT = process.env.CONNECTORS_PORT || 3000;

// Webhook-based connectors mount as Express routers
app.use('/whatsapp', require('./whatsapp/index'));
app.use('/sms', require('./sms/index'));

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

app.listen(PORT, () => {
  console.log(`[connectors] webhook server listening on :${PORT}`);
});

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
