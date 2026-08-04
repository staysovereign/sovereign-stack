import { useState, useEffect } from "react";
import { api } from "../api.js";

const LEVEL_DESCRIPTIONS = [
  "Observing silently. Not yet making decisions.",
  "Noticing first patterns. Suggestions will appear here.",
  "Regular recommendations with full data shown.",
  "Auto-weighting enabled (opt-in). Your Council still overrides everything.",
  "Filter fully personalized. Near-zero false signals.",
];

export default function Advisor() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [resetting, setResetting] = useState(false);

  function load() {
    api.advisor().then(setData).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function handleDismiss(id) {
    await api.advisorDismiss(id).catch((e) => setError(e.message));
    load();
  }

  async function handleReset() {
    setResetting(true);
    try {
      await api.advisorReset();
      setConfirming(false);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setResetting(false);
    }
  }

  if (!data && !error) return <div className="column"><p style={{ color: "var(--muted)" }}>Loading…</p></div>;

  const m = data?.maturity;
  const acc = data?.accuracy;

  return (
    <div className="column">
      <div className="room-header">
        <h1 className="room-title">The Advisor</h1>
        <p className="room-subtitle">A local model that learns your definition of urgency from your actions, never from message content.</p>
      </div>

      {error && <div className="error-banner" style={{ marginBottom: "1rem" }}>{error}</div>}

      {m && (
        <>
          <div className="card">
            <div className="row-between" style={{ marginBottom: "0.5rem" }}>
              <h2>{m.name}</h2>
              <span className="badge">Level {m.level} / 4</span>
            </div>
            <p style={{ fontSize: "0.875rem", color: "var(--muted)", marginBottom: "1rem" }}>
              {LEVEL_DESCRIPTIONS[m.level]}
            </p>
            <div className="maturity-bar">
              {[0, 1, 2, 3, 4].map((i) => (
                <div key={i} className={`maturity-pip ${i <= m.level ? "maturity-pip--filled" : ""}`} />
              ))}
            </div>
            {m.installed_at && (
              <p style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.5rem" }}>
                Watching since {new Date(m.installed_at).toLocaleDateString()}
              </p>
            )}
          </div>

          {acc && acc.total > 0 && (
            <div className="advisor-stats-grid">
              <div className="advisor-stat">
                <span className="advisor-stat-value">{acc.total}</span>
                <span className="advisor-stat-label">Signals</span>
              </div>
              <div className="advisor-stat">
                <span className="advisor-stat-value">{acc.rate !== null ? `${Math.round(acc.rate * 100)}%` : "—"}</span>
                <span className="advisor-stat-label">Accuracy</span>
              </div>
              <div className="advisor-stat">
                <span className="advisor-stat-value">{acc.false_positives}</span>
                <span className="advisor-stat-label">False passes</span>
              </div>
              <div className="advisor-stat">
                <span className="advisor-stat-value">{acc.false_negatives}</span>
                <span className="advisor-stat-label">Missed urgent</span>
              </div>
            </div>
          )}

          {acc && acc.total === 0 && (
            <p className="notice" style={{ marginTop: "1rem" }}>
              The Advisor has no signals yet. It builds its model from your response patterns — every message you reply to (or don't) teaches it.
            </p>
          )}
        </>
      )}

      {data?.suggestion && (
        <>
          <hr className="divider" />
          <h2 style={{ marginBottom: "1rem" }}>A suggestion</h2>
          <div className="suggestion-card">
            <p className="suggestion-body">"{data.suggestion.body}"</p>
            <p style={{ fontSize: "0.75rem", color: "var(--muted)", marginBottom: "1rem" }}>
              Based on your anonymized behavioral patterns. No message content was read.
            </p>
            <div className="row">
              <button className="btn btn-primary" style={{ fontSize: "0.85rem" }} onClick={() => handleDismiss(data.suggestion.id)}>
                Got it
              </button>
              <button className="btn btn-ghost" style={{ fontSize: "0.85rem" }} onClick={() => handleDismiss(data.suggestion.id)}>
                Not relevant
              </button>
            </div>
          </div>
        </>
      )}

      <hr className="divider" />

      <div>
        <h3 style={{ marginBottom: "0.5rem" }}>Privacy</h3>
        <p style={{ fontSize: "0.875rem", color: "var(--muted)", marginBottom: "1rem" }}>
          The Advisor stores sender identities as one-way SHA-256 hashes. It never reads message content. All inference runs locally via Ollama — no data ever leaves your machine.
        </p>

        {!confirming ? (
          <button className="btn btn-danger" onClick={() => setConfirming(true)}>
            Reset the Advisor
          </button>
        ) : (
          <div className="card" style={{ borderColor: "var(--danger)" }}>
            <p style={{ fontSize: "0.875rem", marginBottom: "1rem" }}>
              This will delete all {data?.accuracy?.total ?? 0} signals and all suggestions. The Advisor will restart from zero. Are you sure?
            </p>
            <div className="row">
              <button className="btn btn-danger" disabled={resetting} onClick={handleReset}>
                {resetting ? "Resetting…" : "Yes, reset"}
              </button>
              <button className="btn btn-ghost" onClick={() => setConfirming(false)}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
