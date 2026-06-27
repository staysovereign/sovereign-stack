import { useState, useEffect } from "react";
import { api } from "../api.js";

export default function Settings() {
  const [s, setS] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.settings().then(setS).catch((e) => setError(e.message));
  }, []);

  function set(key, value) {
    setS((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.settingsUpdate({
        quiet_hours_enabled: s.quiet_hours_enabled === "true" ? "true" : "false",
        quiet_hours_start: s.quiet_hours_start || "22:00",
        quiet_hours_end: s.quiet_hours_end || "07:00",
        quiet_hours_tz: (s.quiet_hours_tz || "UTC").trim(),
        quiet_hours_threshold_count: String(s.quiet_hours_threshold_count || "5"),
        quiet_hours_threshold_window_seconds: String(s.quiet_hours_threshold_window_seconds || "1800"),
      });
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (!s) {
    return <div className="column"><p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>Loading…</p></div>;
  }

  const enabled = s.quiet_hours_enabled === "true";
  const windowMin = Math.max(1, Math.round((Number(s.quiet_hours_threshold_window_seconds) || 1800) / 60));

  return (
    <div className="column">
      <div className="room-header">
        <h1 className="room-title">Settings</h1>
        <p className="room-subtitle">Quiet hours and how urgency reaches you.</p>
      </div>

      <form className="card" style={{ display: "grid", gap: "1.25rem" }} onSubmit={save}>
        <div className="row" style={{ gap: "0.6rem" }}>
          <input
            type="checkbox" id="qh" className="toggle" checked={enabled}
            onChange={(e) => set("quiet_hours_enabled", e.target.checked ? "true" : "false")}
          />
          <label htmlFor="qh" style={{ fontWeight: 600 }}>Enable quiet hours</label>
        </div>
        <p style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: "-0.7rem" }}>
          During quiet hours, urgent messages wait quietly until the window ends. Council members set to “always deliver” still reach you.
        </p>

        <div className="row" style={{ gap: "1rem", flexWrap: "wrap", opacity: enabled ? 1 : 0.5 }}>
          <div className="form-group">
            <label className="label">From</label>
            <input type="time" value={s.quiet_hours_start || "22:00"} disabled={!enabled}
              onChange={(e) => set("quiet_hours_start", e.target.value)} />
          </div>
          <div className="form-group">
            <label className="label">Until</label>
            <input type="time" value={s.quiet_hours_end || "07:00"} disabled={!enabled}
              onChange={(e) => set("quiet_hours_end", e.target.value)} />
          </div>
          <div className="form-group" style={{ flex: 1, minWidth: 160 }}>
            <label className="label">Timezone</label>
            <input value={s.quiet_hours_tz || "UTC"} disabled={!enabled} placeholder="America/Bogota"
              onChange={(e) => set("quiet_hours_tz", e.target.value)} />
          </div>
        </div>

        <hr className="divider" />

        <div className="form-group">
          <label className="label">Wake me anyway if it's a flood</label>
          <div className="row" style={{ gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <input type="number" min="1" style={{ width: 70 }}
              value={s.quiet_hours_threshold_count || "5"}
              onChange={(e) => set("quiet_hours_threshold_count", e.target.value)} />
            <span style={{ color: "var(--muted)", fontSize: "0.9rem" }}>urgent messages within</span>
            <input type="number" min="1" style={{ width: 70 }} value={windowMin}
              onChange={(e) => set("quiet_hours_threshold_window_seconds", String((Number(e.target.value) || 1) * 60))} />
            <span style={{ color: "var(--muted)", fontSize: "0.9rem" }}>minutes</span>
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="row" style={{ justifyContent: "flex-end", gap: "0.75rem", alignItems: "center" }}>
          {saved && <span style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Saved.</span>}
          <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </div>
  );
}
