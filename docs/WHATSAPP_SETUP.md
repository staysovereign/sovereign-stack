# WhatsApp Bridge Setup (Matrix + mautrix-whatsapp)

This is the **most involved** connector to set up, but once done it's the most powerful: WhatsApp messages reach the real you, transparently, and Sovereign filters them like any other platform.

WhatsApp has no official self-hosting API, so Sovereign bridges it through **Matrix**:

```
WhatsApp  ⇄  mautrix-whatsapp (bridge)  ⇄  Synapse (Matrix homeserver)  ⇄  Sovereign connector (/sync)
```

- **Synapse** — a private, federation-disabled Matrix homeserver.
- **mautrix-whatsapp** — logs into your real WhatsApp (like WhatsApp Web) and bridges each chat into a Matrix "portal room".
- **Sovereign's WhatsApp connector** — logs into Synapse as the `@sovereign` user, joins those portal rooms, and forwards messages to the engine. Replies are sent back into the same room, which the bridge relays to WhatsApp.

> **Important:** this guide targets the modern **bridgev2** mautrix-whatsapp (the current `:latest`). Its config format differs completely from older versions — let the bridge **generate** its config, then edit it (don't hand-write it).

> **Run order matters.** The bridge must generate its registration file *before* Synapse starts with the appservice configured. Follow the steps in order.

---

## Prerequisites

- The core stack already works (`docker compose up -d`).
- Docker Compose v2, `openssl`.
- Your phone with WhatsApp installed and signed in (you'll link the bridge as a companion device, like WhatsApp Web).

Throughout, the Matrix server name is `sovereign.local` (fine for local/LAN use) and the bridge user is `@sovereign:sovereign.local`. Adjust if you set a custom `MATRIX_SERVER_NAME`.

---

## Step 1 — Prepare the Synapse config

```bash
./setup.sh --whatsapp
```

This seeds `synapse/homeserver.yaml` from the committed template, fills in fresh Synapse secrets, and records `MATRIX_HOMESERVER_URL` in `.env`. (The real `synapse/homeserver.yaml` and the bridge files are gitignored — they hold secrets.)

## Step 2 — Initialize the Synapse data volume

Synapse runs as UID **991** and reads its config from the `synapse_data` volume, so copy the config in and fix ownership:

```bash
docker compose --profile whatsapp run --rm --user root --entrypoint sh \
  -v "$(pwd)/synapse/homeserver.yaml:/seed/homeserver.yaml:ro" \
  -v "$(pwd)/synapse/log.config:/seed/log.config:ro" \
  synapse -c 'mkdir -p /data/appservices && cp /seed/homeserver.yaml /data/ && cp /seed/log.config /data/ && chown -R 991:991 /data'
```

> If you skip the `chown`, Synapse fails with `PermissionError: /data/signing.key`.

## Step 3 — Generate the bridge config

Let mautrix-whatsapp write its default config, then exit:

```bash
docker compose --profile whatsapp run --rm mautrix
# -> "Wrote example config to /data/config.yaml ... Modify that config file"
```

The config lands in `./mautrix/config.yaml` (the `./mautrix` dir is bind-mounted to the bridge's `/data`). It'll be owned by the bridge user; make it editable:

```bash
docker compose --profile whatsapp run --rm --user root --entrypoint chown mautrix -R "$(id -u):$(id -g)" /data
```

## Step 4 — Configure the bridge

Edit `./mautrix/config.yaml` and change these fields:

```yaml
database:
    type: sqlite3-fk-wal
    uri: file:/data/mautrix-whatsapp.db?_txlock=immediate

homeserver:
    address: http://synapse:8008
    domain: sovereign.local

appservice:
    address: http://mautrix:29318
    hostname: 0.0.0.0          # required for Docker
    port: 29318

# (under the bridge permissions section)
    permissions:
        "sovereign.local": user
        "@sovereign:sovereign.local": admin
```

Everything else can stay default. (Encryption is off by default, which is what the Sovereign connector expects.)

## Step 5 — Generate the registration & make it readable

```bash
docker compose --profile whatsapp run --rm mautrix          # generates ./mautrix/registration.yaml
docker compose --profile whatsapp run --rm --user root --entrypoint chown mautrix -R "$(id -u):$(id -g)" /data
chmod 644 mautrix/registration.yaml                          # Synapse (UID 991) must be able to read it
```

`registration.yaml` is mounted into Synapse at `/data/appservices/whatsapp-registration.yaml` (already wired in `docker-compose.yml`), and its `as_token`/`hs_token` match the ones the bridge wrote into `config.yaml`.

## Step 6 — Start Synapse and the bridge

```bash
docker compose --profile whatsapp up -d synapse
# wait until healthy:
docker inspect --format '{{.State.Health.Status}}' sovereign-stack-synapse-1

docker compose --profile whatsapp up -d mautrix
docker compose logs mautrix | grep -i "Bridge started"
```

You should see `Homeserver -> appservice connection works` and `Bridge started`.

## Step 7 — Create the `@sovereign` user + access token

The connector and the reply path log into Synapse as `@sovereign`. Create the user and capture a token into `.env`:

```bash
PASS=$(openssl rand -hex 16)
docker compose exec -T synapse register_new_matrix_user -c /data/homeserver.yaml -u sovereign -p "$PASS" -a http://localhost:8008

TOKEN=$(docker compose exec -T synapse curl -s -XPOST http://localhost:8008/_matrix/client/v3/login \
  -H 'Content-Type: application/json' \
  -d "{\"type\":\"m.login.password\",\"identifier\":{\"type\":\"m.id.user\",\"user\":\"sovereign\"},\"password\":\"$PASS\"}" \
  | grep -oE '"access_token":"[^"]+"' | sed -E 's/.*:"([^"]+)"/\1/')

# write them into .env
sed -i "s|^MATRIX_ACCESS_TOKEN=.*|MATRIX_ACCESS_TOKEN=${TOKEN}|" .env
grep -q '^MATRIX_PASSWORD=' .env || echo "MATRIX_PASSWORD=${PASS}" >> .env
```

## Step 8 — Link your WhatsApp (pairing code)

We use the bridge's **provisioning API** with a phone **pairing code** (no QR rendering needed). Replace `+57XXXXXXXXXX` with the WhatsApp number you're linking.

```bash
SECRET=$(docker compose exec -T mautrix cat /data/config.yaml | grep -E 'shared_secret:' | head -1 | awk '{print $2}')
docker compose exec -T core python3 - "$SECRET" "+57XXXXXXXXXX" <<'PY'
import json, urllib.request, urllib.parse, sys, time
sec, phone = sys.argv[1], sys.argv[2]
uid = urllib.parse.quote('@sovereign:sovereign.local')
def call(path, body=None):
    url = 'http://mautrix:29318'+path+'?user_id='+uid
    data = json.dumps(body).encode() if body is not None else b'{}'
    req = urllib.request.Request(url, method='POST', headers={'Authorization':'Bearer '+sec,'Content-Type':'application/json'}, data=data)
    return json.load(urllib.request.urlopen(req))
d = call('/_matrix/provision/v3/login/start/phone'); lid, sid = d['login_id'], d['step_id']
d = call('/_matrix/provision/v3/login/step/'+lid+'/'+sid+'/user_input', {'phone_number': phone})
print('\n>>> PAIRING CODE:', d['display_and_wait']['data'], '<<<\n', flush=True)
sid = d['step_id']
print('Enter it NOW in WhatsApp: Settings > Linked Devices > Link a Device > "Link with phone number instead"', flush=True)
for _ in range(120):
    w = call('/_matrix/provision/v3/login/step/'+lid+'/'+sid+'/display_and_wait')
    if w.get('type') == 'complete':
        print('LOGGED IN:', w.get('instructions')); break
    time.sleep(2)
else:
    print('Timed out — re-run to get a fresh code.')
PY
```

**Enter the code quickly (within ~60 s).** If you enter it late the bridge can hit a known refresh bug (`missing <link_code_pairing_wrapped_primary_ephemeral_pub>`) and fail — just re-run the snippet for a fresh code.

> Prefer scanning a QR? Log into Synapse as `@sovereign` (password from `.env`) with a Matrix client like Element (you'd need to publish Synapse's port 8008 first), DM `@whatsappbot:sovereign.local`, send `login`, and scan the QR. The pairing-code method above avoids exposing a port.

On success the bridge logs `Login completed successfully` and `Connected to WhatsApp socket`.

## Step 9 — Bring up the whole stack

From now on, always start Sovereign **with the whatsapp profile** so Synapse + the bridge run alongside everything else:

```bash
docker compose --profile whatsapp up -d      # or: make up-whatsapp
```

The connector logs `Matrix sync starting` and will `joined portal room …` as your chats receive messages. Test it: have someone send you a WhatsApp message containing an urgency keyword (e.g. `urgente`) — it should reach your dumbphone, and your `r …` reply should land back in that WhatsApp chat.

---

## How it behaves

- **Portal rooms are created on demand** — a chat appears only when it next receives a message (not all at once). The **first** message in a brand-new chat may be missed (the connector joins a moment after the room is created); the next message comes through.
- **Group messages are held by default**, on WhatsApp just like Telegram/email (the "Hold all group messages" Decree). To let a specific person through even in groups, add them to your **Council** (Tier 1 overrides the group hold). Disabling that Decree affects **all** platforms.
- The bridge stays linked like a WhatsApp Web companion. Keep the phone online occasionally; WhatsApp unlinks idle companion devices after ~14 days.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Legacy bridge config detected … migrator is not set` (crash loop) | You're on bridgev2 with an old config. Regenerate it (Step 3–4). |
| `PermissionError: /data/signing.key` (Synapse) | `synapse_data` not owned by 991. Re-run the `chown -R 991:991 /data` from Step 2. |
| Synapse can't read registration / appservice not loaded | `registration.yaml` not world-readable. `chmod 644 mautrix/registration.yaml`, restart Synapse. |
| Pairing fails: `missing <link_code_pairing_wrapped_primary_ephemeral_pub>` | Code entered too late. Re-run Step 8 and enter the fresh code within ~60 s. |
| Connector idle / not forwarding | `MATRIX_ACCESS_TOKEN` not set in `.env` (Step 7), or you started without `--profile whatsapp`. |
| Nothing happens on the first message to a new contact | Expected — send a second message (portal-creation timing). |
