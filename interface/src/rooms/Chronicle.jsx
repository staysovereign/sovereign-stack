import { useState, useEffect } from "react";
import { api } from "../api.js";

const TIER_LABELS = { council: "Council", decree: "Decrees", advisor: "Advisor", default: "Default" };

function fmt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function Chronicle() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    api.chronicle(days).then(setData).catch((e) => setError(e.message));
  }, [days]);

  const t = data?.totals;
  const passRate = t?.total ? Math.round((t.passed / t.total) * 100) : null;

  return (
    <div className="column">
      <div className="room-header row-between">
        <div>
          <h1 className="room-title">The Chronicle</h1>
          <p className="room-subtitle">Honest numbers. No gamification.</p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          style={{ width: "auto", fontSize: "0.8rem" }}
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={365}>Last year</option>
        </select>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {!data ? (
        <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Loading…</p>
      ) : (
        <>
          <div className="chronicle-stats">
            <div className="chronicle-stat">
              <div className="chronicle-stat-value">{t.total}</div>
              <div className="chronicle-stat-label">Messages received</div>
            </div>
            <div className="chronicle-stat">
              <div className="chronicle-stat-value">{t.passed}</div>
              <div className="chronicle-stat-label">Reached you</div>
            </div>
            <div className="chronicle-stat">
              <div className="chronicle-stat-value">{t.held}</div>
              <div className="chronicle-stat-label">Held in Vault</div>
            </div>
            <div className="chronicle-stat">
              <div className="chronicle-stat-value">{passRate !== null ? `${passRate}%` : "—"}</div>
              <div className="chronicle-stat-label">Pass rate</div>
            </div>
          </div>

          {data.by_platform.length > 0 && (
            <>
              <h2 style={{ marginBottom: "1rem" }}>By platform</h2>
              <div className="card" style={{ marginBottom: "2rem", padding: "0 1.25rem" }}>
                {data.by_platform.map((p) => {
                  const pct = p.total ? Math.round((p.passed / p.total) * 100) : 0;
                  return (
                    <div key={p.platform} style={{ display: "grid", gridTemplateColumns: "100px 1fr auto", gap: "1rem", alignItems: "center", padding: "0.75rem 0", borderBottom: "1px solid var(--border)" }}>
                      <span className="badge" style={{ textAlign: "center" }}>{p.platform}</span>
                      <div style={{ background: "var(--surface)", borderRadius: "2px", height: "6px", overflow: "hidden" }}>
                        <div style={{ width: `${pct}%`, height: "100%", background: "var(--accent)", borderRadius: "2px" }} />
                      </div>
                      <span style={{ fontSize: "0.8rem", color: "var(--muted)", whiteSpace: "nowrap" }}>{p.passed} / {p.total}</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          <div className="row-between" style={{ marginBottom: "0.75rem" }}>
            <h2>Recent decisions</h2>
            <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>last 50</span>
          </div>

          {data.recent.length === 0 ? (
            <div className="empty-state">No messages yet.</div>
          ) : (
            <div className="card" style={{ padding: "0 1.25rem" }}>
              {data.recent.map((entry) => (
                <div key={entry.id} className="chronicle-entry">
                  <span className={`chronicle-decision chronicle-decision--${entry.decision}`}>{entry.decision}</span>
                  <span>
                    {entry.sender_name || entry.sender_id}
                    <span style={{ color: "var(--muted)", fontSize: "0.78rem", marginLeft: "0.4rem" }}>
                      via {entry.platform} · {TIER_LABELS[entry.tier_triggered] ?? entry.tier_triggered}
                    </span>
                  </span>
                  <span className="chronicle-ts">{fmt(entry.evaluated_at)}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
