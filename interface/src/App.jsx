import { useState, useEffect } from "react";
import { api } from "./api.js";
import Onboarding from "./rooms/Onboarding.jsx";
import Vault from "./rooms/Vault.jsx";
import Council from "./rooms/Council.jsx";
import Decrees from "./rooms/Decrees.jsx";
import Advisor from "./rooms/Advisor.jsx";
import Chronicle from "./rooms/Chronicle.jsx";
import "./styles/app.css";

const ROOMS = [
  { id: "vault",     label: "The Vault" },
  { id: "council",   label: "The Council" },
  { id: "decrees",   label: "The Decrees" },
  { id: "advisor",   label: "The Advisor" },
  { id: "chronicle", label: "The Chronicle" },
];

export default function App() {
  const [room, setRoom] = useState("vault");
  const [onboarding, setOnboarding] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api.council()
      .then((data) => {
        if (data.count === 0) setOnboarding(true);
      })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);

  if (checking) return null;

  if (onboarding) {
    return <Onboarding onComplete={() => setOnboarding(false)} />;
  }

  const Room = {
    vault:     Vault,
    council:   Council,
    decrees:   Decrees,
    advisor:   Advisor,
    chronicle: Chronicle,
  }[room];

  return (
    <div className="sovereign-shell">
      <header className="sovereign-header">
        <div className="column row-between">
          <span className="sovereign-wordmark">Sovereign</span>
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
    </div>
  );
}
