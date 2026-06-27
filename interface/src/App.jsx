import { useState, useEffect } from "react";
import { api, clearToken, setUnauthorizedHandler } from "./api.js";
import { Setup, Login, ChangePassword } from "./Auth.jsx";
import Onboarding from "./rooms/Onboarding.jsx";
import Vault from "./rooms/Vault.jsx";
import Council from "./rooms/Council.jsx";
import Decrees from "./rooms/Decrees.jsx";
import Advisor from "./rooms/Advisor.jsx";
import Chronicle from "./rooms/Chronicle.jsx";
import Settings from "./rooms/Settings.jsx";
import "./styles/app.css";

const ROOMS = [
  { id: "vault",     label: "The Vault" },
  { id: "council",   label: "The Council" },
  { id: "decrees",   label: "The Decrees" },
  { id: "advisor",   label: "The Advisor" },
  { id: "chronicle", label: "The Chronicle" },
  { id: "settings",  label: "Settings" },
];

export default function App() {
  // auth gate: "checking" | "setup" | "login" | "ready"
  const [auth, setAuth] = useState("checking");
  const [room, setRoom] = useState("vault");
  const [onboarding, setOnboarding] = useState(false);
  const [checkingOnb, setCheckingOnb] = useState(true);
  const [showChange, setShowChange] = useState(false);

  // Decide setup vs login vs ready on load; re-login if a session expires.
  useEffect(() => {
    setUnauthorizedHandler(() => setAuth("login"));
    api.authStatus()
      .then((s) => setAuth(s.authenticated ? "ready" : s.configured ? "login" : "setup"))
      .catch(() => setAuth("login"));
  }, []);

  // Once authenticated, check whether the Council is empty (first-run onboarding).
  useEffect(() => {
    if (auth !== "ready") return;
    setCheckingOnb(true);
    api.council()
      .then((data) => setOnboarding(data.count === 0))
      .catch(() => {})
      .finally(() => setCheckingOnb(false));
  }, [auth]);

  function logout() {
    api.authLogout().catch(() => {});
    clearToken();
    setAuth("login");
  }

  if (auth === "checking") return null;
  if (auth === "setup") return <Setup onDone={() => setAuth("ready")} />;
  if (auth === "login") return <Login onDone={() => setAuth("ready")} />;
  if (checkingOnb) return null;
  if (onboarding) return <Onboarding onComplete={() => setOnboarding(false)} />;

  const Room = {
    vault:     Vault,
    council:   Council,
    decrees:   Decrees,
    advisor:   Advisor,
    chronicle: Chronicle,
    settings:  Settings,
  }[room];

  return (
    <div className="sovereign-shell">
      <header className="sovereign-header">
        <div className="column">
          <div className="sovereign-topbar">
            <span className="sovereign-wordmark">Sovereign</span>
            <div className="sovereign-account">
              <button className="account-btn" onClick={() => setShowChange(true)} title="Change password">Password</button>
              <span className="account-sep" aria-hidden="true">·</span>
              <button className="account-btn" onClick={logout} title="Sign out">Lock</button>
            </div>
          </div>
          <nav className="sovereign-nav">
            {ROOMS.map((r) => (
              <button
                key={r.id}
                className={`nav-btn ${room === r.id ? "nav-btn--active" : ""}`}
                onClick={() => setRoom(r.id)}
              >
                {r.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="sovereign-main">
        <Room />
      </main>

      {showChange && <ChangePassword onClose={() => setShowChange(false)} />}
    </div>
  );
}
