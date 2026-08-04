# Sovereign Appliance — Onboarding Roadmap

**Status:** Design doc / roadmap. Nothing here is built yet. This describes how a
person *without deep technical knowledge* turns a Raspberry Pi they own into a
running Sovereign stack.

> Guiding constraint: Sovereign runs only on **hardware you physically own** (see
> README → Hardware options). This roadmap is about making that easy, never about
> hosting it for anyone.

---

## The vision

A **first-boot provisioning appliance**. A small, separate "Sovereign Setup" web
app runs *before* the stack is up, walks the owner through configuring every
service, handles the painful bridge logins, writes `.env` + the bridge configs,
then presses **Start** and hands off to the real Sovereign interface.

Two design decisions frame everything:

1. **Setup is a separate UI from the daily UI.** The main interface is
   deliberately calm — "a study, not a cockpit," five rooms, no clutter. Setup is
   inherently a cockpit (tokens, QR codes, toggles). It also has to run when the
   stack *isn't up yet*. So it lives in its own one-time, utilitarian service and
   never pollutes the daily surface.
2. **Installer first, image later.** We ship a one-line installer for Raspberry
   Pi OS now (80% of the dream, low maintenance), and only later bake a prebuilt
   flashable image once the wizard UX is proven.

---

## Scope: two levels of "the dream"

| Level | What the user does | Effort / upkeep | Phase |
|---|---|---|---|
| **One-line installer** | Flash stock Raspberry Pi OS Lite (64-bit), then run one `curl … \| bash` | Moderate build, **low** upkeep | **1 (now)** |
| **Prebuilt image** | Flash a Sovereign image with Raspberry Pi Imager, boot, open `sovereign.local` | Higher build, **higher** upkeep (image size, updates, multi-model) | 2 (later) |

Installer-first means the magic arrives quickly and we defer image-maintenance
until the setup flow is solid.

---

## Architecture

### The Setup Service (new component)

A small web app — call it `setup/` — that is the only thing running after install,
before the stack. Responsibilities:

- Serve a wizard on the LAN at `http://sovereign.local:PORT` (mDNS via avahi so
  the owner never needs the IP; fall back to "check your router for the IP").
- Collect configuration and **write `.env`** and the bridge config files.
- Orchestrate Docker: it needs the Docker socket (or a thin privileged helper) to
  run `docker compose up -d` with the right profile, and to stream logs back.
- Drive the interactive integrations (secrets, Synapse first-run, WhatsApp QR).
- Stay reachable afterward for **reconfigure** and **update** (see below).

Tech: keep it boring and light (it runs on a Pi and must start with no
dependencies pre-provisioned). A single small container, or a systemd-run static
binary + a tiny HTTP server. It must be first-run password-protected and
**LAN-only** — it can write secrets and control Docker, so it is powerful.

### What already exists to build on

- **`setup.sh`** — checks prerequisites (docker, openssl, compose), copies
  `.env.example` → `.env`, and **auto-generates secrets** (e.g.
  `WHATSAPP_BRIDGE_SECRET`). The `--whatsapp` flag pulls in the bridge stack. The
  Setup Service should reuse/extend this logic rather than reinvent it.
- **Compose profiles** — `core`, `interface`, `connectors` run always; `synapse`,
  `mautrix`, `mautrix-meta` are gated behind the `whatsapp` profile. The wizard
  simply chooses whether to start with `--profile whatsapp`.
- **Makefile** — `setup`, `up`, `up-whatsapp`, `update`, `backup`, `restore`,
  `ollama-pull`, `whatsapp-qr` are ready-made actions the Setup Service can call.
- **In-app Settings room** (`core/api/settings_api.py`) — already edits a subset
  of runtime config (quiet hours, etc.). The wizard owns *first-run* + *bridges*;
  day-to-day tweaks stay in the calm UI. Avoid duplicating; draw the line clearly.
- **Bridge provisioning** — mautrix exposes a login/provisioning API; the wizard
  triggers WhatsApp login and shows the QR / pair code, polling for success.

---

## The onboarding flow (wizard screens)

1. **Welcome + set a password** for the Setup Service (LAN-only, but still gated).
2. **The dumb phone** — enter `DUMB_PHONE_NUMBER`; pick the SMS path
   (`gammu` for a GSM HAT/modem, or `off` to hold everything in the Vault for
   now). Detect a serial/USB modem if present and offer to write a gammu config.
3. **Connectors** — Telegram bot token; email IMAP creds; each optional and
   testable ("Send test / verify" before moving on).
4. **WhatsApp (optional)** — start the bridge, show the QR/pair code, poll until
   linked. This is tractable for non-technical users.
5. **Instagram/Meta (advanced, optional)** — *honestly labelled.* Meta auth is
   cookie-based (sessionid/csrftoken) with ban risk; a non-technical user pulling
   cookies from devtools is a non-starter. Keep it off the happy path with a
   clear "this one is technical and risky" warning. Do not pretend it's one-click.
6. **The Advisor** — pick an Ollama model sized to the hardware (tiny model on
   4 GB; skip entirely to save RAM). Pull runs in the background.
7. **Seed the Council** (optional) and confirm defaults (groups held, quiet hours).
8. **Review & Start** — write configs, `docker compose --profile … up -d`, stream
   health, then hand off with a link to the daily UI.

---

## The genuinely hard parts (and how each is handled)

- **Secrets** — never ship defaults; generate on first run (extend `setup.sh`).
- **Synapse first-run** — appservice tokens, registration files world-readable,
  the `synapse_data` UID-991 chown. All scriptable; the wizard does it silently.
- **WhatsApp pairing** — provisioning API + QR in the browser; solvable.
- **Meta/Instagram** — the real wall (cookies + ban risk). Ships as *advanced*,
  not core. Setting expectations honestly is part of the design.
- **Finding the box** — avahi/mDNS `sovereign.local`; documented IP fallback.
- **Updates** — a non-technical owner needs a one-button **Update Sovereign**
  (`git pull` + `docker compose pull` + recreate; wraps `make update`).
  Onboarding that's easy but leaves people stranded on old code is a half-solution.
- **Backups** — surface `make backup`/`restore` as buttons so the SQLite DB and
  bridge sessions are recoverable (losing bridge sessions = re-pairing everything).
- **Security** — Setup Service is LAN-only, password-gated, and ideally can be
  disabled/hidden once setup completes (re-enable to reconfigure).

---

## Roadmap

- **M1 — Installer skeleton.** `curl … | bash` on Raspberry Pi OS Lite: install
  Docker + compose, clone the repo, install the Setup Service as a systemd unit,
  bring up mDNS, open the wizard. No bridges yet.
- **M2 — Core wizard.** Screens 1–3, 6–8: dumb phone/SMS, connectors, Advisor,
  Council, Review & Start. Reuses `setup.sh` + Makefile actions. This alone makes
  a **no-bridge** Sovereign truly non-technical.
- **M3 — WhatsApp in the wizard.** Bridge start + QR pairing + success polling.
- **M4 — Update/backup buttons + reconfigure mode.** Long-term livability.
- **M5 — Meta (advanced).** Guarded cookie flow with heavy warnings; optional.
- **M6 — Prebuilt image.** `pi-gen` build → flash-and-go, once M1–M4 are proven.

---

## Non-goals

- No hosted/managed offering, ever. Owned hardware only.
- No attempt to make **Meta/Instagram** one-click — it's honestly "advanced."
- The Setup Service does **not** absorb the daily Settings room; it owns first-run
  and bridges, the calm UI owns everyday tweaks.

---

## Open questions

- Docker control from the Setup Service: mount the Docker socket vs. a minimal
  privileged helper? (Security vs. simplicity.)
- Does the Setup Service live *inside* the compose project (chicken-and-egg on
  first boot) or as a host-level systemd service that *drives* compose? (Leaning
  host-level for M1.)
- Model catalogue: which Ollama models to offer per detected RAM, and how to make
  that choice legible to a non-technical owner.
