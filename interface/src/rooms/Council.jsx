import { useState, useEffect } from "react";
import { api } from "../api.js";

const PLATFORMS = ["whatsapp", "telegram", "email", "sms"];

const EMPTY_FORM = { platform: "whatsapp", sender_id: "", name: "", quiet_hours_override: false };

export default function Council() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [nudge, setNudge] = useState(null);

  function load() {
    api.council().then(setData).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function handleAdd(e) {
    e.preventDefault();
    if (!form.sender_id.trim() || !form.name.trim()) return;
    setSaving(true);
    setError(null);
    setNudge(null);
    try {
      const res = await api.councilAdd({ ...form, sender_id: form.sender_id.trim(), name: form.name.trim() });
      if (res.nudge) setNudge(res.nudge);
      setForm(EMPTY_FORM);
      setAdding(false);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleOverride(member) {
    await api.councilUpdate(member.id, { quiet_hours_override: !member.quiet_hours_override });
    load();
  }

  async function toggleMute(member) {
    await api.councilUpdate(member.id, { muted: !member.muted }).catch((e) => setError(e.message));
    load();
  }

  async function handleRemove(id) {
    if (!confirm("Remove this member from your Council?")) return;
    await api.councilRemove(id).catch((e) => setError(e.message));
    load();
  }

  return (
    <div className="column">
      <div className="room-header row-between">
        <div>
          <h1 className="room-title">The Council</h1>
          <p className="room-subtitle">Their messages always reach you, no matter what.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
          {adding ? "Cancel" : "+ Add member"}
        </button>
      </div>

      {nudge && <div className="notice">{nudge}</div>}
      {error && <div className="error-banner" style={{ marginBottom: "1rem" }}>{error}</div>}

      {adding && (
        <form className="card" style={{ marginBottom: "1.5rem", display: "grid", gap: "1rem" }} onSubmit={handleAdd}>
          <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
            <div className="form-group" style={{ flex: "0 0 auto" }}>
              <label className="label">Platform</label>
              <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}>
                {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 180 }}>
              <label className="label">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Mamá" required />
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label className="label">Sender ID</label>
              <input value={form.sender_id} onChange={(e) => setForm({ ...form, sender_id: e.target.value })} placeholder="+1234567890 or @username" required />
            </div>
          </div>
          <div className="row">
            <input type="checkbox" id="qho" className="toggle" checked={form.quiet_hours_override} onChange={(e) => setForm({ ...form, quiet_hours_override: e.target.checked })} />
            <label htmlFor="qho" style={{ fontSize: "0.875rem" }}>Always deliver, even during quiet hours</label>
          </div>
          <div style={{ textAlign: "right" }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Adding…" : "Add to Council"}</button>
          </div>
        </form>
      )}

      {!data ? (
        <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Loading…</p>
      ) : data.members.length === 0 ? (
        <div className="empty-state">Your Council is empty.</div>
      ) : (
        <div className="card" style={{ padding: "0 1.25rem" }}>
          {data.members.map((m) => (
            <div key={m.id} className={`council-member${m.muted ? " is-muted" : ""}`}>
              <div style={m.muted ? { opacity: 0.5 } : undefined}>
                <div className="council-name">{m.name}</div>
                <div className="council-detail">{m.platform} · {m.sender_id}</div>
                <div className="row" style={{ gap: "0.4rem", marginTop: "0.25rem" }}>
                  {m.muted
                    ? <span className="badge" title="Skipped at The Council — governed by the Decrees instead">muted</span>
                    : m.quiet_hours_override && <span className="badge">always on</span>}
                </div>
              </div>
              <div className="council-actions">
                {!m.muted && (
                  <input
                    type="checkbox"
                    className="toggle"
                    checked={m.quiet_hours_override}
                    onChange={() => toggleOverride(m)}
                    title="Always deliver during quiet hours"
                  />
                )}
                <button
                  className="btn btn-ghost"
                  style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                  onClick={() => toggleMute(m)}
                  title={m.muted
                    ? "Re-seat: their messages reach you directly again"
                    : "Mute: keep them on the Council but route their messages through the Decrees"}
                >
                  {m.muted ? "Unmute" : "Mute"}
                </button>
                <button className="btn btn-ghost" style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", color: "var(--danger)", borderColor: "var(--danger)" }} onClick={() => handleRemove(m.id)}>
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {data && data.count >= data.soft_cap && (
        <p className="notice" style={{ marginTop: "1rem" }}>
          Your Council has {data.count} members. An unlimited Council is no Council. Keep it to people who truly matter.
        </p>
      )}
    </div>
  );
}
