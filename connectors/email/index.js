const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');
const { dispatch, buildMessage } = require('../shared/normalize');

const config = {
  host: process.env.EMAIL_IMAP_HOST,
  port: parseInt(process.env.EMAIL_IMAP_PORT || '993', 10),
  secure: process.env.EMAIL_IMAP_SECURE !== 'false',
  auth: {
    user: process.env.EMAIL_IMAP_USER,
    pass: process.env.EMAIL_IMAP_PASS,
  },
  logger: false,
};

if (!config.host || !config.auth.user || !config.auth.pass) {
  console.warn('[email] EMAIL_IMAP_HOST / USER / PASS not set — connector idle');
  return;
}

async function processMessage(client, uid) {
  const { content } = await client.download(uid, undefined, { uid: true });
  const parsed = await simpleParser(content);

  const from = parsed.from?.value?.[0] || {};
  const body = parsed.text || parsed.html || '';

  const normalized = buildMessage({
    platform: 'email',
    sender: {
      id: from.address || 'unknown',
      name: from.name || null,
      email: from.address || null,
      phone: null,
    },
    content: {
      type: 'text',
      body: `Subject: ${parsed.subject || '(no subject)'}\n\n${body.slice(0, 2000)}`,
    },
    group: null,
    metadata: {
      subject: parsed.subject || null,
      message_id: parsed.messageId || null,
      date: parsed.date?.toISOString() || null,
    },
  });

  try {
    await dispatch(normalized);
  } catch (err) {
    console.error('[email] dispatch failed:', err.message);
  }
}

async function start() {
  const client = new ImapFlow(config);

  client.on('error', (err) => {
    console.error('[email] IMAP error:', err.message);
  });

  await client.connect();
  console.log('[email] connected, listening via IDLE...');

  const lock = await client.getMailboxLock('INBOX');
  try {
    // Process unseen messages on startup
    const uids = await client.search({ seen: false });
    for (const uid of uids) {
      await processMessage(client, uid);
    }

    // IDLE — fires on new mail
    client.on('exists', async () => {
      const newUids = await client.search({ seen: false });
      for (const uid of newUids) {
        await processMessage(client, uid);
      }
    });

    // Keep IDLE alive indefinitely
    await new Promise(() => {});
  } finally {
    lock.release();
    await client.logout();
  }
}

start().catch((err) => console.error('[email] fatal:', err.message));
