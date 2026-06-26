# SOVEREIGN
### *Govern Your Attention*

> Reclaim the right to be unreachable.

Sovereign is a self-hosted communication router. Messages arrive from all your platforms — WhatsApp, Telegram, Email, SMS — pass through an urgency evaluation engine, and either reach you immediately via SMS on a dumb phone, or wait quietly in the Vault until you choose to engage.

It is not a notification manager. It is a filter with a philosophy.

---

## How it works

```
[WhatsApp]  ─┐
[Telegram]  ─┤   connectors/    →   core (urgency engine)   →   SMS → dumb phone
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
git clone https://github.com/sovereign-stack/sovereign
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

### With WhatsApp

WhatsApp requires a Matrix homeserver (Synapse) and the mautrix-whatsapp bridge:

```bash
# Generates Synapse config, mautrix config, and all shared secrets
./setup.sh --whatsapp

# Start the full stack including Matrix bridge
make up-whatsapp

# Watch for the QR code, then scan with WhatsApp → Linked Devices → Link a Device
make whatsapp-qr
```

That's it. Sovereign initializes its database, seeds default Decrees, and starts listening.

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
| WhatsApp | mautrix-whatsapp Matrix bridge | ✅ stub |
| SMS | Twilio webhook | ✅ |
| Instagram | Unofficial | ⏳ V2 |
| Facebook Messenger | Meta Business API | ⏳ V2 |

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

For WhatsApp, you additionally need to run the mautrix-whatsapp bridge and set `WHATSAPP_BRIDGE_SECRET` and `MATRIX_*` variables. See the spec for full bridge setup.

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

## Deployment paths

| Path | Who | Cost | Control |
|---|---|---|---|
| **Self-hosted** | Technical users | Free | Full sovereignty |
| **Managed cloud** | Anyone | €4.90/month | Zero maintenance |
| **Hybrid** | Power users | Partial | Local data, cloud infra |

### Self-hosted hardware options

| Option | Cost | Notes |
|---|---|---|
| VPS (2 GB RAM) | ~€5/month | Recommended for most users |
| Home server / old laptop | One-time | Always-on required |
| Raspberry Pi 4 + USB GSM modem | ~€60 one-time | Full sovereignty — no Twilio |

### Common operations

```bash
make logs           # Tail all service logs
make status         # Show running containers and health
make backup         # Dump SQLite DB to ./backups/
make update         # Pull latest images and rebuild
make ollama-pull    # Pull the Ollama LLM model
make whatsapp-qr    # Re-display WhatsApp QR code
```

---

## Tech stack

| Component | Technology |
|---|---|
| Core engine | Python 3.12 + FastAPI |
| Platform connectors | Node.js 22 + Express |
| WhatsApp bridge | mautrix-whatsapp (Go) |
| Database | SQLite (WAL mode) |
| AI / Advisor | Ollama (local LLM — never cloud) |
| SMS gateway | Twilio API / gammu (USB GSM modem) |
| Interface | React + Vite *(Layer 6)* |
| Deployment | Docker Compose |
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

*Sovereign. Govern your attention.*
