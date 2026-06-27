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

async function start() {
  const client = new ImapFlow(config);

  client.on('error', (err) => {
    console.error('[email] IMAP error:', err.message);
  });

  await client.connect();
  console.log('[email] connected, listening via IDLE...');

  const lock = await client.getMailboxLock('INBOX');
  try {
    // High-water mark: the highest UID that existed when we connected. New mail
    // always has a higher UID (uidNext - 1 is the current max). We only ever
    // process UIDs above this mark, so the same message is never re-ingested —
    // the previous code re-scanned all unseen mail on every IDLE event, which
    // (combined with random message ids) flooded the Vault with duplicates.
    let lastUid = (client.mailbox.uidNext || 1) - 1;
    let processing = false;

    // search() must return UIDs to match download()'s { uid: true }, otherwise
    // sequence numbers get treated as UIDs and the wrong/empty message is fetched.
    async function processNew() {
      if (processing) return; // serialize; a later IDLE event will catch stragglers
      processing = true;
      try {
        const found = await client.search({ uid: `${lastUid + 1}:*` }, { uid: true });
        // A uid-range search can echo the boundary uid; filter strictly greater.
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

    // Process backlog on startup, bounded by EMAIL_STARTUP_SCAN_LIMIT so a large
    // backlog can't flood delivery on boot. After this, lastUid sits at the
    // current max regardless, so IDLE only ever sees genuinely new mail.
    if (STARTUP_SCAN_LIMIT === 0) {
      console.log(`[email] EMAIL_STARTUP_SCAN_LIMIT=0 — skipping backlog (watermark uid=${lastUid}); only new mail`);
    } else {
      const allUnseen = await client.search({ seen: false }, { uid: true });
      // Keep the most recent ones (search returns UIDs in ascending order).
      const uids =
        STARTUP_SCAN_LIMIT === Infinity ? allUnseen : allUnseen.slice(-STARTUP_SCAN_LIMIT);
      const skipped = allUnseen.length - uids.length;
      console.log(
        `[email] ${allUnseen.length} unseen on startup; processing ${uids.length}` +
          (skipped > 0 ? ` (skipping ${skipped} older — raise EMAIL_STARTUP_SCAN_LIMIT to include them)` : ''),
      );
      for (const uid of uids) {
        try {
          await processMessage(client, uid);
        } catch (err) {
          console.error(`[email] failed to process uid ${uid}:`, err.message);
        }
      }
    }

    // IDLE — fires on new mail; only newly-arrived UIDs are processed.
    client.on('exists', () => {
      processNew().catch((err) => console.error('[email] processNew error:', err.message));
    });

    // Keep IDLE alive indefinitely
    await new Promise(() => {});
  } finally {
    lock.release();
    await client.logout();
  }
}

start().catch((err) => console.error('[email] fatal:', err.message));
