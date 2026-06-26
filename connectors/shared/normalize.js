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

module.exports = { dispatch, buildMessage };
