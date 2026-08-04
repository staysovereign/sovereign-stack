const { v4: uuidv4 } = require('uuid');

/**
 * Post a normalized message to the Sovereign core ingest endpoint.
 * All connectors call this — never POST directly.
 */
async function dispatch(normalizedMessage) {
  const fetch = (await import('node-fetch')).default;
  const url = process.env.CORE_INGEST_URL || 'http://core:8000/ingest';

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(normalizedMessage),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Core rejected message [${res.status}]: ${text}`);
  }

  return res.json();
}

/**
 * Build the normalized message envelope.
 * Each connector fills in platform-specific fields;
 * this enforces the shared schema.
 */
function buildMessage({ platform, sender, content, group = null, metadata = {} }) {
  return {
    id: uuidv4(),
    timestamp: new Date().toISOString(),
    platform,
    sender,
    content,
    group,
    metadata,
  };
}

/**
 * Loose phone-number equality. Gateways report inbound numbers inconsistently
 * (national vs E.164), e.g. InfiniReach sends "3246530369" while the configured
 * number is "+573246530369". Compare the trailing significant digits so
 * "3246530369", "573246530369" and "+57 324 653 0369" all match.
 */
function samePhone(a, b) {
  const da = String(a || '').replace(/\D/g, '');
  const db = String(b || '').replace(/\D/g, '');
  if (da.length < 7 || db.length < 7) return false;
  const n = Math.min(da.length, db.length);
  return da.slice(-n) === db.slice(-n);
}

module.exports = { dispatch, buildMessage, samePhone };
