import { useState } from "react";
import { api } from "../api.js";

const PLATFORMS = ["whatsapp", "telegram", "email", "sms"];

export default function Onboarding({ onComplete }) {
  const [members, setMembers] = useState([{ platform: "whatsapp", sender_id: "", name: "" }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function addRow() {
    setMembers((prev) => [...prev, { platform: "whatsapp", sender_id: "", name: "" }]);
  }

  function updateRow(i, field, value) {
    setMembers((prev) => prev.map((m, idx) => (idx === i ? { ...m, [field]: value } : m)));
  }

  function removeRow(i) {
    setMembers((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const valid = members.filter((m) => m.sender_id.trim() && m.name.trim());
    if (!valid.length) { setError("Add at least one person."); return; }
    setSaving(true);
    setError(null);
    try {
      for (const m of valid) {
        await api.councilAdd({ platform: m.platform, sender_id: m.sender_id.trim(), name: m.name.trim() });
      }
      onComplete();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="onboarding">
      <div className="onboarding-wordmark">Sovereign</div>

      <h1 className="onboarding-question">
        Who are the people whose message should always reach you,<br />
        no matter what, no matter when?
      </h1>
      <p className="onboarding-sub">Take your time. This list matters.</p>

      <form className="onboarding-form" onSubmit={handleSubmit}>
        {members.map((m, i) => (
          <div key={i} className="card" style={{ display: "grid", gap: "0.75rem" }}>
            <div className="row-between">
              <span className="label" style={{ marginBottom: 0 }}>Council member {i + 1}</span>
              {members.length > 1 && (
                <button type="button" className="btn btn-ghost" style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem" }} onClick={() => removeRow(i)}>
                  Remove
                </button>
              )}
            </div>
            <div className="form-group">
              <label className="label">Name</label>
              <input value={m.name} onChange={(e) => updateRow(i, "name", e.target.value)} placeholder="Mamá" required />
            </div>
            <div className="row" style={{ gap: "0.5rem" }}>
              <div className="form-group" style={{ flex: "0 0 auto" }}>
                <label className="label">Platform</label>
                <select value={m.platform} onChange={(e) => updateRow(i, "platform", e.target.value)}>
                  {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="label">Sender ID / phone / email</label>
                <input value={m.sender_id} onChange={(e) => updateRow(i, "sender_id", e.target.value)} placeholder="+1234567890 or @username" required />
              </div>
            </div>
          </div>
        ))}

        <button type="button" className="btn btn-ghost" onClick={addRow} style={{ alignSelf: "flex-start" }}>
          + Add another
        </button>

        {error && <div className="error-banner">{error}</div>}

        <button type="submit" className="btn btn-primary" disabled={saving} style={{ alignSelf: "flex-end", padding: "0.6rem 1.5rem" }}>
          {saving ? "Building your Council…" : "Begin"}
        </button>
      </form>
    </div>
  );
}
