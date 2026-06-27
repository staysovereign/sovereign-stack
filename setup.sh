#!/usr/bin/env bash
# Sovereign — first-time setup
# Run once before `docker compose up -d`
#
# Usage:
#   ./setup.sh              # core stack only
#   ./setup.sh --whatsapp   # include Matrix WhatsApp bridge

set -euo pipefail

WHATSAPP=0
for arg in "$@"; do
  [[ "$arg" == "--whatsapp" ]] && WHATSAPP=1
done

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'
info()  { echo -e "${GREEN}▸${RESET} $*"; }
warn()  { echo -e "${YELLOW}⚠${RESET} $*"; }
error() { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }

# ── Prerequisites ─────────────────────────────────────────────────────────────
command -v docker   >/dev/null 2>&1 || error "Docker is not installed."
command -v openssl  >/dev/null 2>&1 || error "openssl is required."
docker compose version >/dev/null 2>&1 || error "Docker Compose v2 is required."

info "Starting Sovereign setup…"

# ── .env ─────────────────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env
  warn ".env created from .env.example — edit it before continuing."
  warn "At minimum set: DUMB_PHONE_NUMBER, TWILIO_*, and one connector token."
  echo ""
  echo "Press Enter when .env is ready, or Ctrl-C to abort."
  read -r
fi

# ── Generate random secrets for .env if placeholders remain ──────────────────
gen_secret() { openssl rand -hex 32; }

patch_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=CHANGE_ME" .env 2>/dev/null; then
    sed -i "s|^${key}=CHANGE_ME.*|${key}=${value}|" .env
    info "Generated ${key}"
  fi
}

# Twilio webhook secret (used to validate Twilio signature in connectors)
patch_env "TWILIO_WEBHOOK_SECRET" "$(gen_secret)"

# ── Ollama model ──────────────────────────────────────────────────────────────
info "Pulling Ollama LLM (llama3.2) — this may take several minutes on first run…"
docker compose pull ollama 2>/dev/null || true
# Model pull happens after first start (see Makefile: make ollama-pull)

# ── WhatsApp bridge setup (Matrix + mautrix-whatsapp, bridgev2) ────────────────
# This prepares the Synapse homeserver config. The bridge itself (mautrix-whatsapp
# bridgev2) generates its own config/registration and is linked interactively, so
# the remaining steps are documented in docs/WHATSAPP_SETUP.md.
if [[ "$WHATSAPP" -eq 1 ]]; then
  echo ""
  info "Preparing Matrix homeserver config for the WhatsApp bridge…"

  MATRIX_SERVER_NAME=$(grep "^MATRIX_SERVER_NAME=" .env 2>/dev/null | cut -d= -f2 | tr -d '"')
  MATRIX_SERVER_NAME=${MATRIX_SERVER_NAME:-sovereign.local}

  # The real synapse/homeserver.yaml is gitignored (it holds secrets). Seed it
  # from the committed template, then fill in fresh Synapse secrets.
  [[ -f synapse/homeserver.yaml ]] || cp synapse/homeserver.yaml.example synapse/homeserver.yaml
  sed -i \
    -e "s|SOVEREIGN_MATRIX_SERVER_NAME|${MATRIX_SERVER_NAME}|g" \
    -e "s|SOVEREIGN_REGISTRATION_SHARED_SECRET|$(gen_secret)|g" \
    -e "s|SOVEREIGN_MACAROON_SECRET|$(gen_secret)|g" \
    -e "s|SOVEREIGN_FORM_SECRET|$(gen_secret)|g" \
    synapse/homeserver.yaml

  grep -q "^MATRIX_HOMESERVER_URL=" .env || echo "MATRIX_HOMESERVER_URL=http://synapse:8008" >> .env

  info "Synapse config ready (synapse/homeserver.yaml)."
  echo ""
  warn "WhatsApp needs a few more guided steps: generate the bridge config, register"
  warn "it with Synapse, create the @sovereign user, and link WhatsApp with a pairing"
  warn "code. Follow:  docs/WHATSAPP_SETUP.md"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
info "Setup complete."
echo ""
echo "  Start Sovereign:        docker compose up -d"
if [[ "$WHATSAPP" -eq 1 ]]; then
  echo "  Start with WhatsApp:    docker compose --profile whatsapp up -d"
fi
echo "  Open the interface:     http://localhost"
echo "  Pull Ollama model:      make ollama-pull   (after first start)"
echo "  View logs:              make logs"
echo ""
