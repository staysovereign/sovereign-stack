.PHONY: setup up up-whatsapp down logs status backup restore ollama-pull whatsapp-qr update

# ── Setup ──────────────────────────────────────────────────────────────────────
setup:
	@chmod +x setup.sh && ./setup.sh

setup-whatsapp:
	@chmod +x setup.sh && ./setup.sh --whatsapp

# ── Lifecycle ─────────────────────────────────────────────────────────────────
up:
	docker compose up -d

up-whatsapp:
	docker compose --profile whatsapp up -d

down:
	docker compose --profile whatsapp down

logs:
	docker compose --profile whatsapp logs -f

status:
	docker compose --profile whatsapp ps

# ── Ollama ────────────────────────────────────────────────────────────────────
# Pull the default model (llama3.2). Change OLLAMA_MODEL in .env to override.
ollama-pull:
	@MODEL=$$(grep '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2 | tr -d '"'); \
	MODEL=$${MODEL:-llama3.2}; \
	echo "Pulling $$MODEL…"; \
	docker compose exec ollama ollama pull "$$MODEL"

# ── WhatsApp ──────────────────────────────────────────────────────────────────
# Watch the mautrix log until the QR code appears, then scan with WhatsApp.
whatsapp-qr:
	docker compose --profile whatsapp logs -f mautrix

# ── Data ──────────────────────────────────────────────────────────────────────
# Backup: dump the SQLite DB to ./backups/sovereign-YYYY-MM-DD.db
backup:
	@mkdir -p backups
	@DATE=$$(date +%Y-%m-%d); \
	docker compose exec core sh -c \
	  "sqlite3 /data/sovereign.db .dump" > "backups/sovereign-$$DATE.sql" && \
	echo "Backed up to backups/sovereign-$$DATE.sql"

# Restore from a backup: make restore FILE=backups/sovereign-2025-01-01.sql
restore:
	@test -n "$(FILE)" || (echo "Usage: make restore FILE=backups/filename.sql" && exit 1)
	@echo "Restoring from $(FILE) — this will overwrite the current database."
	@read -p "Continue? [y/N] " c && [ "$$c" = "y" ]
	docker compose exec -T core sh -c \
	  "sqlite3 /data/sovereign.db < /dev/stdin" < "$(FILE)"

# ── Maintenance ───────────────────────────────────────────────────────────────
update:
	docker compose --profile whatsapp pull
	docker compose --profile whatsapp build --pull
	docker compose --profile whatsapp up -d
	@echo "Update complete. Check 'make status' and 'make logs'."
