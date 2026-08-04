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

// How many pre-existing unseen messages to process on startup.
//   unset  → default of 10 (safe: a large backlog can't flood delivery)
//   0      → skip the backlog entirely (only mail arriving after start)
//   N      → the N most recent unseen messages
//   "all"  → no limit (process every unseen message)
function parseStartupScanLimit() {
  const raw = process.env.EMAIL_STARTUP_SCAN_LIMIT;
  if (raw === undefined || raw === '') return 10;
  if (raw.toLowerCase() === 'all') return Infinity;
  const n = parseInt(raw, 10);
  if (Number.isNaN(n) || n < 0) {
    console.warn(`[email] invalid EMAIL_STARTUP_SCAN_LIMIT "${raw}" — using default of 10`);
    return 10;
  }
  return n;
}

const STARTUP_SCAN_LIMIT = parseStartupScanLimit();

async function processMessage(client, uid) {
  const downloaded = await client.download(uid, undefined, { uid: true });
  if (!downloaded || !downloaded.content) {
    console.warn(`[email] no content for uid ${uid}, skipping`);
    return;
  }
  const parsed = await simpleParser(downloaded.content);

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

// High-water-mark UID, kept across reconnects within this process so we never
// re-ingest old mail and never miss mail that arrived during a disconnect.
let lastUid = null;

async function runOnce() {
  const client = new ImapFlow(config);
  client.on('error', (err) => console.error('[email] IMAP error:', err.message));

  await client.connect();
  await client.mailboxOpen('INBOX');
  const currentMax = (client.mailbox.uidNext || 1) - 1;
  const firstConnect = lastUid === null;

  if (firstConnect) {
    // Establish the watermark per EMAIL_STARTUP_SCAN_LIMIT.
    if (STARTUP_SCAN_LIMIT === 0) {
      lastUid = currentMax;
      console.log(`[email] connected — skipping backlog (watermark uid=${lastUid}); only new mail`);
    } else {
      const allUnseen = await client.search({ seen: false }, { uid: true });
      const uids = STARTUP_SCAN_LIMIT === Infinity ? allUnseen : allUnseen.slice(-STARTUP_SCAN_LIMIT);
      const skipped = allUnseen.length - uids.length;
      console.log(
        `[email] connected — ${allUnseen.length} unseen; processing ${uids.length}` +
          (skipped > 0 ? ` (skipping ${skipped} older — raise EMAIL_STARTUP_SCAN_LIMIT to include them)` : ''),
      );
      for (const uid of uids) {
        try {
          await processMessage(client, uid);
        } catch (err) {
          console.error(`[email] failed to process uid ${uid}:`, err.message);
        }
      }
      lastUid = currentMax;
    }
  } else {
    console.log(`[email] reconnected (watermark uid=${lastUid})`);
  }

  let processing = false;
  async function processNew() {
    if (processing) return; // serialize; a later IDLE event catches stragglers
    processing = true;
    try {
      // search() must return UIDs to match download()'s { uid: true }.
      const found = await client.search({ uid: `${lastUid + 1}:*` }, { uid: true });
      const fresh = (found || []).filter((u) => u > lastUid);
      for (const uid of fresh) {
        try {
          await processMessage(client, uid);
        } catch (err) {
          console.error(`[email] failed to process uid ${uid}:`, err.message);
        }
        if (uid > lastUid) lastUid = uid;
      }
    } finally {
      processing = false;
    }
  }

  // IDLE — fires on new mail; only newly-arrived UIDs are processed.
  client.on('exists', () => processNew().catch((e) => console.error('[email] processNew error:', e.message)));

  // After a reconnect, immediately catch up on anything that arrived while away.
  if (!firstConnect) await processNew();

  // Block until the connection closes, then let run() reconnect.
  await new Promise((resolve) =>
    client.on('close', () => {
      console.warn('[email] IMAP connection closed');
      resolve();
    }),
  );
}

async function run() {
  for (;;) {
    try {
      await runOnce();
    } catch (err) {
      console.error('[email] connection error:', err.message);
    }
    await new Promise((r) => setTimeout(r, 15000));
    console.log('[email] reconnecting…');
  }
}

run().catch((err) => console.error('[email] fatal:', err.message));
