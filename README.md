# SOVEREIGN
### *Govern Your Attention*

> Reclaim the right to be unreachable.

Sovereign is a self-hosted communication router. Messages arrive from all your platforms — WhatsApp, Instagram, Telegram, Email, SMS — pass through an urgency evaluation engine, and either reach you immediately via SMS on a dumb phone, or wait quietly in the Vault until you choose to engage.

It is not a notification manager. It is a filter with a philosophy.

---

## How it works

```
[WhatsApp]  ─┐
[Instagram] ─┤
[Telegram]  ─┼   connectors/    →   core (urgency engine)   →   SMS → dumb phone
[Email]     ─┤   (Node.js)          (Python / FastAPI)           ↑
[SMS]       ─┘                           │                       └── reply routing
                                         ↓
                                       Vault
                                  (held messages)
```

Every message is evaluated through three tiers:

| Tier | Name | Description |
|---|---|---|
| 1 | **The Council** | Your curated VIP list. Their messages always reach you. |
| 2 | **The Decrees** | Your rules. Keywords, frequency, platform filters. |
| 3 | **The Advisor** | A local AI that learns your urgency patterns over time. |

If no tier claims urgency, the message waits in **The Vault** — held, never deleted.

---

## Vocabulary

| Term | Meaning |
|---|---|
| **The Council** | Your VIP list. Small by design (soft cap: 10). |
| **The Decrees** | Your rules. `IF [condition] THEN [pass/hold]`. |
| **The Advisor** | Local AI behavioral model (Ollama). Never cloud inference. |
| **The Vault** | Everything held. Waiting for your attention, on your schedule. |
| **The Chronicle** | Honest log of every decision Sovereign made. |
| **The Realm** | Your Sovereign instance — your config, your data, your rules. |
| **The Territory** | Your dumb phone. The calm device that is your interface with the world. |
| **The Commonwealth** | The Sovereign community sharing Decrees and insights. |

---

## Quick start

```bash
git clone https://github.com/zerohashcrbn/sovereign-stack.git
cd sovereign

# First time only — generates secrets, checks prerequisites
./setup.sh

# Edit .env: set DUMB_PHONE_NUMBER, TWILIO_*, and one connector token
# Then start everything
docker compose up -d

# Pull the Ollama model (runs in the background, takes a few minutes)
make ollama-pull
```

Open the interface at **http://localhost**. On first load, Sovereign asks you one question: who should always reach you?

> 📖 **New to Sovereign?** The [User Guide](docs/USER_GUIDE.md) explains every screen and how to configure it, in plain language with examples — written for non-technical users.

### With WhatsApp & Instagram (Matrix bridges)

WhatsApp and Instagram are bridged through a private Matrix homeserver (Synapse) plus mautrix bridges (mautrix-whatsapp and mautrix-meta), so the real you stays reachable and Sovereign filters transparently. A few guided steps each — generate the bridge config, register it, create the Matrix user, and link your account (WhatsApp via a pairing code, Instagram via session cookies):

```bash
./setup.sh --whatsapp            # prepares the shared Synapse config
```

> 📖 Then follow the **[Matrix Bridge Setup guide](docs/WHATSAPP_SETUP.md)** — a complete, step-by-step walkthrough for both bridges, with troubleshooting.

Once linked, always start the stack **with the whatsapp profile** so Synapse and the bridge run too:

```bash
docker compose --profile whatsapp up -d      # or: make up-whatsapp
```

---

## Architecture

Seven layers, built in order:

| # | Layer | Status | Description |
|---|---|---|---|
| 1 | **Ingestion** | ✅ Done | Platform connectors normalize all messages into a single schema |
| 2 | **Urgency Engine** | ✅ Done | Three-tier evaluation: Council → Decrees → Advisor |
| 3 | **Delivery** | ✅ Done | SMS formatter, quiet hours, Twilio + gammu gateway |
| 4 | **Reply Routing** | ✅ Done | Dumb phone SMS commands routed back to originating platform |
| 5 | **The Advisor** | ✅ Done | Local Ollama behavioral model, learns from your response patterns |
| 6 | **The Interface** | ✅ Done | Browser-only React UI: Vault, Council, Decrees, Advisor, Chronicle |
| 7 | **Deployment** | ✅ Done | Full Docker Compose stack; setup script; Makefile; WhatsApp bridge profile |

---

## Platform connectors

| Platform | Method | Status |
|---|---|---|
| Telegram | Official Bot API (polling) | ✅ |
| Email | IMAP IDLE | ✅ |
| WhatsApp | mautrix-whatsapp Matrix bridge | ✅ |
| SMS | Twilio webhook | ✅ |
| Instagram | mautrix-meta Matrix bridge | ✅ |
| Facebook Messenger | mautrix-meta (messenger mode) | ⏳ same bridge, not enabled |

---

## Configuration

Copy `.env.example` to `.env` and fill in your values. Minimum viable config:

```env
DUMB_PHONE_NUMBER=+1234567890
TELEGRAM_BOT_TOKEN=your-bot-token    # from @BotFather
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+1987654321
```

For WhatsApp and Instagram, you additionally run the Matrix bridges (Synapse + mautrix-whatsapp / mautrix-meta); the `@sovereign` user's `MATRIX_ACCESS_TOKEN` is created during setup, and `BRIDGE_SELF_IDS` lists your own account ids so messages you send yourself aren't surfaced. See the **[Matrix Bridge Setup guide](docs/WHATSAPP_SETUP.md)**.

### Email connector tuning

The email connector watches your inbox and routes new mail through the engine. To stop a large backlog of existing unread mail from flooding delivery on startup, set how many pre-existing unseen messages it processes on boot:

```env
# unset → 10 (safe default)   ·   0 → skip backlog, only new mail
# N → the N most recent unseen ·   all → process every unseen message
EMAIL_STARTUP_SCAN_LIMIT=10
```

Mail arriving *after* startup is always processed live, regardless of this setting.

### SMS delivery gateway

Sovereign can send the urgent SMS through one of several gateways, chosen with `SMS_GATEWAY` (or auto-detected in the order **twilio → infinireach → android → gammu**):

| `SMS_GATEWAY` | Who it's for | Setup |
|---|---|---|
| `twilio` | Quickest start | Set `TWILIO_*` credentials |
| `infinireach` | No USB modem; want a hosted relay that sends via your own SIM | [InfiniReach](https://infinireach.io) account + `INFINIREACH_API_KEY` |
| `android` | No USB modem; prefer a fully local LAN setup | An Android phone with a SIM running an HTTP SMS-gateway app on your LAN |
| `gammu` | Full sovereignty | A USB GSM modem + `GAMMU_CONFIG_PATH` |

Both `infinireach` and `android` use a phone's SIM, so SMS is **local-to-local** — avoiding the foreign-number A2P filtering that blocks cloud long codes in some countries (e.g. Colombia).

**InfiniReach replies (inbound):** to route your dumb-phone replies back, configure InfiniReach's `message.inbound` webhook to:

```
POST  https://<your-public-host>/infinireach/webhook
```

The connectors port must be reachable from the internet (port-forward or a tunnel like ngrok/cloudflared). Optionally set `INFINIREACH_WEBHOOK_SECRET` and append `?secret=…` to the URL to reject unauthenticated calls. Outbound works without any of this; only replies need the public webhook.

**Android phone gateway:** install an on-phone HTTP SMS-gateway app in **local server** mode, put the phone on the same network as Sovereign, then point `ANDROID_SMS_GATEWAY_URL` at the app's **full send endpoint**:

```env
SMS_GATEWAY=android
ANDROID_SMS_GATEWAY_URL=http://<phone-ip>:8080/send-sms
ANDROID_SMS_GATEWAY_USER=...   # only if your app requires auth
ANDROID_SMS_GATEWAY_PASS=...
```

Sovereign POSTs JSON `{"phone": "<dumb-phone-number>", "message": "<text>"}` to that exact URL and treats an HTTP `2xx` (without a `{"success": false}` body) as sent — so any gateway app exposing that contract works. The path varies by app (`/send-sms`, `/message`, …); use whatever endpoint your app documents. The phone sends from its own SIM, so local-to-local SMS isn't subject to the foreign-number A2P filtering that blocks cloud providers in some countries — a good stand-in until a GSM modem arrives.

> **Keep the gateway phone reachable.** Because it runs over your LAN, the phone must be awake and on the network when an urgent SMS fires — keep it on power and exempt the app from battery optimization. If it's briefly unreachable a send fails, but the message is never lost: it falls back to the Vault.

*Inbound replies (dumb phone → original chat).* Most local gateway apps (Simple SMS Gateway, Traccar SMS Gateway, …) are **send-only** — they can't forward the SMS the SIM *receives*, so your reply would never get back to WhatsApp/Instagram/etc. Pair the sender with a Play-Store **incoming-SMS forwarder** (e.g. *SMS Forwarder* / *AutoForwardText* — pick one that allows a plain-HTTP URL on a LAN IP) on the same phone, and point it at Sovereign:

```
POST  http://<this-host-lan-ip>:4000/android/webhook
```

Sovereign accepts the common forwarder payloads automatically (it reads the sender from `from`/`sender`/`phoneNumber`/… and the text from `message`/`text`/`body`/…). A text from the dumb phone is routed to `/reply` (sent back to the original chat); anything else is ingested as an inbound SMS. Optionally set `ANDROID_SMS_GATEWAY_WEBHOOK_SECRET` and append `?secret=…` to the URL. No public tunnel needed — both phone and host are on your LAN.

---

## Default Decrees

Every new Realm ships with three Decrees:

| Priority | Name | Condition | Action |
|---|---|---|---|
| 1 | Hold all group messages | Message is in a group | **HOLD** — always, no override |
| 10 | Urgency keywords | emergency, urgent, hospital, accident, llámame, ayuda, please call | **PASS** |
| 20 | Frequency escalation | Same sender 3+ messages in 10 minutes | **PASS** |

You can add, edit, or disable Decrees through the Interface at `http://localhost` after running `docker compose up`.

---

## SMS command reference

When your dumb phone receives an urgent message, you have a 15-minute reply window. Just text back your reply. After the window expires, use commands:

```
r Sounds good, call you back    → reply to most recent urgent message
r mama I'll be home soon        → reply to last message from contact "mama"
r 2 On my way                   → reply to 2nd most recent message
list                            → see recent held messages
read 3                          → read full content of message #3
status                          → vault summary
```

Sovereign sends a confirmation SMS back after each command.

---

## Deployment

Sovereign has one deployment model: your server, your machine, your rules. There is no managed cloud, no subscription, no company holding your messages. That is not a missing feature. It is the point.

### Hardware options

Run Sovereign only on **hardware you physically own**. This is deliberate — there is intentionally **no VPS/cloud option here**. Sovereign holds live, impersonation-grade **platform session tokens** (WhatsApp / Instagram / Telegram) and your full triaged **message history**. On rented infrastructure those bytes sit on someone else's computer, subject to their access and jurisdiction — which contradicts the whole promise. A VPS would give you software sovereignty but not data sovereignty; for this tool, that's not enough.

| Option | Cost | Notes |
|---|---|---|
| **Raspberry Pi 5 (8 GB) + GSM/LTE HAT** | ~€100 one-time | **Recommended appliance.** Full sovereignty — runs everything, SMS from your own SIM via gammu |
| Old laptop / mini-PC / home server | Reuse what you own | Ideal if you already have one: capable, always-on, at home |
| Raspberry Pi 4 (8 GB) | ~€60 one-time | Budget floor for the full stack; the Advisor just runs slower |

**Sizing.** Everything but the Advisor fits in ~1 GB; **Ollama** (the local LLM) is the one heavy piece (~3–4 GB while generating). So:

- **Full stack incl. Advisor:** Raspberry Pi 5 (8 GB) recommended; Pi 4 (8 GB) is the practical floor (LLM is slow but runs async, so it never blocks routing). On 4 GB, use a tiny model (`llama3.2:1b`) or offload Ollama to another machine via `OLLAMA_URL`.
- **Without the Advisor:** 2 GB is plenty. You lose only AI *suggestions* — the gatekeeping (Council + Decrees) doesn't use the LLM.
- **Always:** 64-bit OS (arm64 — all images are arm64; no Pi Zero/1/2/3), and **run from an SSD/NVMe, not an SD card** — Synapse + SQLite write often enough to kill SD cards.

**SMS radio for gammu (USB modem vs. GSM HAT).** For a permanent Pi appliance a **GSM/LTE HAT is the better choice** than a USB dongle: it's integrated (nothing to knock loose), has a proper antenna connector, and is tidier. Caveats worth planning for:

- **Prefer a 4G LTE HAT** (e.g. SIM7600-based) over 2G-only modules (SIM800/900) — 2G/3G networks are being shut down in many countries; SMS-over-LTE keeps working. Check whether your carrier still runs 2G before buying a 2G board.
- **Power:** cellular radios draw large current bursts on transmit. Use a strong PSU (the Pi 5 27 W supply) and, if the HAT has a dedicated power input, feed it — under-powering causes random resets mid-send.
- **Connection:** HATs present either as a UART on the GPIO header (`/dev/ttyS0`/`/dev/ttyAMA0`, enable the serial port + free it from the login console) or as USB (`/dev/ttyUSB*`). gammu handles both.
- **Docker:** pass the device into the `core` container (e.g. `devices: ["/dev/ttyUSB2:/dev/ttyUSB2"]`) and point `GAMMU_CONFIG_PATH` at a gammu config for it.

### Common operations

```bash
make logs           # Tail all service logs
make status         # Show running containers and health
make backup         # Dump SQLite DB to ./backups/
make update         # Pull latest images and rebuild
make ollama-pull    # Pull the Ollama LLM model
make whatsapp-qr    # Tail the bridge logs (WhatsApp pairing / login)
make up-whatsapp    # Start full stack with WhatsApp and Instagram bridges
```

---

## Tech stack

| Component | Technology |
|---|---|
| Core engine | Python 3.12 + FastAPI |
| Platform connectors | Node.js 22 + Express |
| WhatsApp / Instagram bridges | mautrix-whatsapp + mautrix-meta (Go) |
| Database | SQLite (WAL mode) |
| AI / Advisor | Ollama (local LLM — never cloud) |
| SMS gateway | Twilio / InfiniReach / Android HTTP / gammu (USB GSM modem) |
| Interface | React + Vite |
| Deployment | Docker Compose + setup.sh + Makefile |
| License | AGPL-3.0 |

---

## Core guardrail

> **Sovereign never silently drops a message.**
> Every message either passes through or is held in the Vault.
> Nothing is deleted. Nothing is lost.

---

## License

[AGPL-3.0](LICENSE) — anyone can run it, modify it, and must keep modifications open source. Commercial use requires contribution back.

---

## Community

- [Wiki](../../wiki) — full documentation: installation, platform setup, Decrees guide, troubleshooting
- [Discussions](../../discussions) — the Commonwealth: setups, Decree sharing, questions, philosophy
- [staysovereign.io](https://staysovereign.io) — project home

---

*Sovereign. Govern your attention.*
