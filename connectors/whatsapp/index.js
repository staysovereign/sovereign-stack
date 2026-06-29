/**
 * WhatsApp connector — Matrix sync client for the mautrix-whatsapp bridge.
 *
 * mautrix-whatsapp bridges WhatsApp <-> Matrix: incoming WhatsApp messages
 * appear as events in Matrix "portal" rooms on Synapse. This connector logs in
 * to Synapse as the @sovereign user, auto-joins those portal rooms, and forwards
 * each incoming message to Sovereign's /ingest. Replies go back via
 * reply/sender.py (_send_whatsapp), which posts into the same room_id.
 *
 * Implemented with the raw Matrix client-server /sync API (no extra deps) since
 * the bridge runs with encryption disabled, so messages are plaintext.
 *
 * Requires:
 *   MATRIX_HOMESERVER_URL  (e.g. http://synapse:8008)
 *   MATRIX_ACCESS_TOKEN    (the @sovereign user's token, from setup)
 *   MATRIX_SERVER_NAME     (e.g. sovereign.local)
 */

const fs = require('fs');
const { dispatch, buildMessage } = require('../shared/normalize');

const HS = (process.env.MATRIX_HOMESERVER_URL || '').replace(/\/$/, '');
const TOKEN = process.env.MATRIX_ACCESS_TOKEN;
const DOMAIN = process.env.MATRIX_SERVER_NAME || 'sovereign.local';
const STORE = process.env.MATRIX_SYNC_STORE || '/data/whatsapp-sync-token';

if (!HS || !TOKEN) {
  console.warn('[whatsapp] MATRIX_HOMESERVER_URL / MATRIX_ACCESS_TOKEN not set — connector idle');
  return;
}

const startedAt = Date.now();
const groupCache = new Map(); // roomId -> isGroup (bool)
let fetchFn;

async function api(method, path, { query = {}, body } = {}) {
  if (!fetchFn) fetchFn = (await import('node-fetch')).default;
  const url = new URL(HS + path);
  url.searchParams.set('access_token', TOKEN);
  for (const [k, v] of Object.entries(query)) if (v != null) url.searchParams.set(k, String(v));
  const res = await fetchFn(url.toString(), {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${await res.text()}`);
  return res.json();
}

function readSince() {
  try { return fs.readFileSync(STORE, 'utf8').trim() || null; } catch { return null; }
}
function writeSince(t) {
  try { fs.writeFileSync(STORE, t); } catch { /* best effort */ }
}

function contentFromEvent(content) {
  switch (content.msgtype) {
    case 'm.text':
      return { type: 'text', body: content.body || '' };
    case 'm.audio':
      return {
        type: 'voice',
        media_url: content.url || null,
        duration_seconds: content.info && content.info.duration ? Math.round(content.info.duration / 1000) : null,
      };
    case 'm.image':
      return { type: 'image', media_url: content.url || null, body: content.body || null };
    case 'm.video':
      return { type: 'video', media_url: content.url || null };
    case 'm.file':
      return { type: 'document', media_url: content.url || null, body: content.body || null };
    default:
      return { type: 'text', body: content.body || '[unsupported message type]' };
  }
}

// Decide group vs DM using the bridge's own room metadata. The reliable signal
// is the WhatsApp chat JID in the `m.bridge` state event: `<id>@g.us` is a group,
// `<phone>@s.whatsapp.net` is a 1:1 DM. (Counting puppets is WRONG: your own
// linked WhatsApp account is also a member of every room, so a DM has two
// @whatsapp_* members.)
async function isGroupRoom(roomId) {
  if (groupCache.has(roomId)) return groupCache.get(roomId);
  let isGroup = null;
  try {
    const state = await api('GET', `/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/state`);
    const bridge = state.find((e) => e.type === 'm.bridge' || e.type === 'uk.half-shot.bridge');
    if (bridge && bridge.content) {
      // com.beeper.room_type is the cross-platform signal both mautrix bridges
      // set: "dm" for a 1:1, anything else is a group. Fall back to the WhatsApp
      // chat JID (only @s.whatsapp.net is a real 1:1; @g.us / @newsletter /
      // status broadcasts / spaces are held like groups).
      const roomType = bridge.content['com.beeper.room_type'];
      const jid = (bridge.content.channel && bridge.content.channel.id) || '';
      if (roomType === 'dm') isGroup = false;
      else if (roomType) isGroup = true;
      else if (jid.endsWith('@s.whatsapp.net')) isGroup = false;
      else if (jid) isGroup = true;
    }
  } catch { /* fall through to heuristic */ }

  if (isGroup === null) {
    // Fallback: count WhatsApp puppets. Your own account's puppet is always a
    // member too, so a 1:1 DM has 2 — treat more than 2 as a group.
    try {
      const data = await api('GET', `/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/joined_members`);
      const wa = Object.keys(data.joined || {}).filter((u) => u.startsWith('@whatsapp_') || u.startsWith('@meta_'));
      isGroup = wa.length > 2;
    } catch { isGroup = false; }
  }

  groupCache.set(roomId, isGroup);
  return isGroup;
}

async function handleEvent(roomId, ev) {
  if (ev.type !== 'm.room.message') return;
  const sender = ev.sender;
  const content = ev.content || {};
  if (!sender || !content.msgtype) return;
  // Only messages authored by bridge puppets (the other party) — this excludes
  // our own @sovereign messages and the bridge bots' notices.
  //   @whatsapp_* → WhatsApp   ·   @meta_* → Instagram (mautrix-meta, instagram mode)
  const platform = sender.startsWith('@whatsapp_') ? 'whatsapp'
    : sender.startsWith('@meta_') ? 'instagram'
    : null;
  if (!platform) return;
  // Skip history/backfill — only handle freshly arrived messages.
  if (ev.origin_server_ts && ev.origin_server_ts < startedAt - 60000) return;

  // WhatsApp puppet MXIDs encode the phone number; Instagram ones don't.
  const m = platform === 'whatsapp' ? sender.match(/^@whatsapp_(\d+):/) : null;
  const phone = m ? `+${m[1]}` : null;

  let name = null;
  try {
    const prof = await api('GET', `/_matrix/client/v3/profile/${encodeURIComponent(sender)}`);
    name = (prof.displayname || '').replace(/\s*\(WA\)\s*$/, '').trim() || null;
  } catch { /* ignore */ }

  const group = (await isGroupRoom(roomId)) ? roomId : null;

  const normalized = buildMessage({
    platform,
    sender: { id: sender, name, phone },
    content: contentFromEvent(content),
    group,
    metadata: { room_id: roomId, event_id: ev.event_id },
  });

  try {
    await dispatch(normalized);
  } catch (err) {
    console.error(`[${platform}] dispatch failed:`, err.message);
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function syncLoop() {
  // Always begin with a full sync (since=null): it lists *all* current room
  // invites — incremental sync won't re-deliver an invite we previously failed
  // to join — while still skipping the message backlog. Then go incremental.
  let since = null;
  console.log('[bridge] Matrix sync starting (full sync to catch all invites)…');

  for (;;) {
    let data;
    try {
      data = await api('GET', '/_matrix/client/v3/sync', { query: { timeout: 30000, since } });
    } catch (err) {
      console.error('[whatsapp] sync error, retry in 10s:', err.message);
      await new Promise((r) => setTimeout(r, 10000));
      continue;
    }

    const rooms = data.rooms || {};

    // Auto-accept invites — the bridge invites us to each portal room. A large
    // backfill (e.g. Instagram) can create many portals at once, so join gently
    // and honor Synapse rate limits (429) with retry — otherwise joins fail and
    // those chats never reach us.
    for (const roomId of Object.keys(rooms.invite || {})) {
      for (let attempt = 0; attempt < 6; attempt++) {
        try {
          await api('POST', `/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/join`);
          console.log('[bridge] joined portal room', roomId);
          await sleep(400); // pace joins to stay under the rate limit
          break;
        } catch (err) {
          const m = /retry_after_ms"?:\s*(\d+)/.exec(err.message);
          if (m) { await sleep(parseInt(m[1], 10) + 250); continue; } // 429 → wait & retry
          console.error('[bridge] join failed', roomId, err.message);
          break;
        }
      }
    }

    // Process messages in joined rooms. On the very first sync (no stored token)
    // we only establish the token and skip the backlog, so we don't re-ingest
    // existing history on (re)start.
    if (since !== null) {
      for (const [roomId, room] of Object.entries(rooms.join || {})) {
        const events = (room.timeline && room.timeline.events) || [];
        for (const ev of events) {
          await handleEvent(roomId, ev);
        }
      }
    }

    since = data.next_batch;
    writeSince(since);
  }
}

syncLoop().catch((err) => console.error('[whatsapp] fatal sync error:', err.message));

module.exports = {};
