import { useState, useEffect } from "react";
import { api } from "../api.js";

const CONDITION_LABELS = {
  GROUP:          "Message is in a group",
  KEYWORD:        "Message contains keyword",
  FREQUENCY:      "Same sender, high frequency",
  PLATFORM:       "Platform is…",
  MESSAGE_TYPE:   "Message type is…",
};

const ACTION_LABELS = {
  PASS: "PASS — deliver immediately",
  HOLD: "HOLD — send to Vault",
};

const EMPTY_FORM = {
  name: "",
  condition: "KEYWORD",
  condition_value: { keywords: [] },
  action: "PASS",
  priority: 50,
};

function DecreeRow({ decree, onChange }) {
  const condLabel = CONDITION_LABELS[decree.condition] ?? decree.condition;
  const val = decree.condition_value;
  let detail = "";
  if (val.keywords?.length) detail = val.keywords.join(", ");
  else if (val.platform) detail = val.platform;
  else if (val.type) detail = val.type;

  async function toggleEnabled() {
    await api.decreesUpdate(decree.id, { enabled: !decree.enabled });
    onChange();
  }

  async function handleDelete() {
    if (!confirm(`Delete "${decree.name}"?`)) return;
    await api.decreesDelete(decree.id).catch((e) => alert(e.message));
    onChange();
  }

  return (
    <div className={`decree-row ${!decree.enabled ? "decree-row--disabled" : ""}`} style={{ opacity: decree.enabled ? 1 : 0.5 }}>
      <span className="decree-priority">#{decree.priority}</span>
      <div>
        <div className="decree-name">
          {decree.name}
          {decree.is_default && <span className="badge" style={{ marginLeft: "0.4rem", fontSize: "0.65rem" }}>default</span>}
        </div>
        <div className="decree-detail">
          {condLabel}{detail ? ` — ${detail}` : ""} → <strong>{decree.action}</strong>
        </div>
      </div>
      <div className="row" style={{ gap: "0.5rem" }}>
        <input type="checkbox" className="toggle" checked={decree.enabled} onChange={toggleEnabled} title={decree.enabled ? "Disable" : "Enable"} />
        {!decree.is_default && (
          <button className="btn btn-ghost" style={{ fontSize: "0.72rem", padding: "0.2rem 0.4rem", color: "var(--danger)", borderColor: "var(--danger)" }} onClick={handleDelete}>
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

export default function Decrees() {
  const [data, setData] = useState(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [keywords, setKeywords] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    api.decrees().then(setData).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function handleCreate(e) {
    e.preventDefault();
    const condition_value = form.condition === "KEYWORD"
      ? { keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean) }
      : form.condition_value;

    setSaving(true);
    setError(null);
    try {
      await api.decreesCreate({ ...form, condition_value });
      setForm(EMPTY_FORM);
      setKeywords("");
      setAdding(false);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="column">
      <div className="room-header row-between">
        <div>
          <h1 className="room-title">The Decrees</h1>
          <p className="room-subtitle">Your rules. Applied before anything else.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
          {adding ? "Cancel" : "+ New Decree"}
        </button>
      </div>

      {error && <div className="error-banner" style={{ marginBottom: "1rem" }}>{error}</div>}

      {adding && (
        <form className="card" style={{ marginBottom: "1.5rem", display: "grid", gap: "1rem" }} onSubmit={handleCreate}>
          <div className="form-group">
            <label className="label">Decree name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Pass hospital messages" required />
          </div>

          <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
            <div className="form-group" style={{ flex: 1, minWidth: 160 }}>
              <label className="label">Condition</label>
              <select value={form.condition} onChange={(e) => setForm({ ...form, condition: e.target.value })}>
                {Object.entries(CONDITION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 120 }}>
              <label className="label">Action</label>
              <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>
                {Object.entries(ACTION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ flex: "0 0 80px" }}>
              <label className="label">Priority</label>
              <input type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} min="1" max="999" />
            </div>
          </div>

          {form.condition === "KEYWORD" && (
            <div className="form-group">
              <label className="label">Keywords (comma-separated)</label>
              <input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="hospital, accident, urgent" />
            </div>
          )}

          <div style={{ textAlign: "right" }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Creating…" : "Create Decree"}</button>
          </div>
        </form>
      )}

      {!data ? (
        <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Loading…</p>
      ) : (
        <div className="card" style={{ padding: "0 1.25rem" }}>
          {data.decrees.length === 0 ? (
            <div className="empty-state">No decrees yet.</div>
          ) : (
            data.decrees.map((d) => <DecreeRow key={d.id} decree={d} onChange={load} />)
          )}
        </div>
      )}

      <p className="notice" style={{ marginTop: "1.5rem" }}>
        Decrees are evaluated in priority order (lowest number first). A matching Decree stops evaluation — the remaining Decrees and Advisor are skipped.
      </p>
    </div>
  );
}
