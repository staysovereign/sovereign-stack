import { useState } from "react";
import { api, setToken } from "./api.js";

function cleanError(e) {
  // Strip the leading "401 " status the api layer prepends, show the detail.
  return String(e?.message || e).replace(/^\d+\s*/, "") || "Something went wrong.";
}

function PasswordScreen({ title, sub, cta, confirm, onSubmit }) {
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    if (confirm && pw !== pw2) {
      setErr("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await onSubmit(pw);
    } catch (err) {
      setErr(cleanError(err));
      setBusy(false);
    }
  }

  return (
    <div className="onboarding">
      <div className="onboarding-wordmark">Sovereign</div>
      <h1 className="onboarding-question">{title}</h1>
      {sub && <p className="onboarding-sub">{sub}</p>}

      <form className="onboarding-form" onSubmit={submit}>
        <div className="card" style={{ display: "grid", gap: "0.75rem" }}>
          <div className="form-group">
            <label className="label">Password</label>
            <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoFocus required />
          </div>
          {confirm && (
            <div className="form-group">
              <label className="label">Confirm password</label>
              <input type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} required />
            </div>
          )}
        </div>

        {err && <div className="error-banner">{err}</div>}

        <button type="submit" className="btn btn-primary" disabled={busy} style={{ alignSelf: "flex-end", padding: "0.6rem 1.5rem" }}>
          {busy ? "…" : cta}
        </button>
      </form>
    </div>
  );
}

export function Setup({ onDone }) {
  return (
    <PasswordScreen
      title="Set a password"
      sub="Protect your dashboard. You'll enter this each time you open Sovereign. At least 6 characters."
      cta="Set password"
      confirm
      onSubmit={async (pw) => {
        const r = await api.authSetup(pw);
        setToken(r.token);
        onDone();
      }}
    />
  );
}

export function Login({ onDone }) {
  return (
    <PasswordScreen
      title="Welcome back"
      sub="Enter your password to govern your attention."
      cta="Unlock"
      onSubmit={async (pw) => {
        const r = await api.authLogin(pw);
        setToken(r.token);
        onDone();
      }}
    />
  );
}

export function ChangePassword({ onClose }) {
  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const [nw2, setNw2] = useState("");
  const [err, setErr] = useState(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    if (nw !== nw2) {
      setErr("New passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.authChange(cur, nw);
      setToken(r.token);
      setDone(true);
    } catch (err) {
      setErr(cleanError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
      <div className="card" style={{ width: "min(420px, 92vw)", display: "grid", gap: "1rem" }} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: 0 }}>Change password</h2>
        {done ? (
          <>
            <p className="notice" style={{ margin: 0 }}>Password updated. Other devices have been signed out.</p>
            <button className="btn btn-primary" style={{ justifySelf: "end" }} onClick={onClose}>Done</button>
          </>
        ) : (
          <form onSubmit={submit} style={{ display: "grid", gap: "0.75rem" }}>
            <div className="form-group">
              <label className="label">Current password</label>
              <input type="password" value={cur} onChange={(e) => setCur(e.target.value)} autoFocus required />
            </div>
            <div className="form-group">
              <label className="label">New password</label>
              <input type="password" value={nw} onChange={(e) => setNw(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="label">Confirm new password</label>
              <input type="password" value={nw2} onChange={(e) => setNw2(e.target.value)} required />
            </div>
            {err && <div className="error-banner">{err}</div>}
            <div className="row" style={{ justifyContent: "flex-end", gap: "0.5rem" }}>
              <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "…" : "Update"}</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
