import { useState, useEffect, useCallback } from "react";
import { api } from "../api.js";

function relativeTime(iso) {
  const diff = (Date.now() - new Date(iso)) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function platformLabel(p) {
  return { whatsapp: "WA", telegram: "TG", email: "EM", sms: "SM" }[p] ?? p.toUpperCase();
}

function VaultItem({ item, onRetrieve }) {
  const [expanded, setExpanded] = useState(false);
  const name = item.sender?.name || item.sender?.id || "Unknown";
  const body = item.content?.body || `[${item.content?.type ?? "media"}]`;

  function handleExpand() {
    setExpanded((v) => !v);
    if (!item.retrieved) onRetrieve(item.id);
  }

  return (
    <div className="vault-item">
      <div className="vault-meta">
        <span className="vault-sender">{name}</span>
        <span className="vault-platform">[{platformLabel(item.platform)}]</span>
        {item.group && <span className="badge">{item.group}</span>}
        <span className="vault-time">{relativeTime(item.held_at)}</span>
      </div>

      {expanded ? (
        <div className="vault-body--expanded">{body}</div>
      ) : (
        <div className="vault-body">{body}</div>
      )}

      <div className="vault-actions">
        <button className="btn btn-ghost" style={{ fontSize: "0.8rem", padding: "0.25rem 0.6rem" }} onClick={handleExpand}>
          {expanded ? "Collapse" : "Read"}
        </button>
        {expanded && (
          <div className="vault-command">
            reply from phone: <strong>r {name.split(" ")[0].toLowerCase()} your message</strong>
          </div>
        )}
        {item.needs_transcription && <span className="badge">🎤 voice</span>}
      </div>
    </div>
  );
}

export default function Vault() {
  const [showRetrieved, setShowRetrieved] = useState(false);
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    api.vault(page, showRetrieved)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, showRetrieved]);

  useEffect(load, [load]);

  async function handleRetrieve(id) {
    await api.vaultRetrieve(id).catch(() => {});
  }

  return (
    <div className="column">
      <div className="room-header">
        <h1 className="room-title">The Vault</h1>
        <p className="room-subtitle">Everything held. Waiting for your attention.</p>
      </div>

      <div className="vault-tabs">
        <button className={`vault-tab ${!showRetrieved ? "vault-tab--active" : ""}`} onClick={() => { setShowRetrieved(false); setPage(1); }}>
          Waiting
        </button>
        <button className={`vault-tab ${showRetrieved ? "vault-tab--active" : ""}`} onClick={() => { setShowRetrieved(true); setPage(1); }}>
          Retrieved
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Loading…</p>
      ) : data?.items?.length === 0 ? (
        <div className="empty-state">
          {showRetrieved ? "Nothing retrieved yet." : "The vault is empty. Everything is reaching you."}
        </div>
      ) : (
        <>
          <div>
            {data.items.map((item) => (
              <VaultItem key={item.id} item={item} onRetrieve={handleRetrieve} />
            ))}
          </div>

          {data.total > data.limit && (
            <div className="row" style={{ marginTop: "1.5rem", justifyContent: "center", gap: "0.5rem" }}>
              <button className="btn btn-ghost" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
                ← Older
              </button>
              <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                {(page - 1) * data.limit + 1}–{Math.min(page * data.limit, data.total)} of {data.total}
              </span>
              <button className="btn btn-ghost" onClick={() => setPage((p) => p + 1)} disabled={page * data.limit >= data.total}>
                Newer →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
