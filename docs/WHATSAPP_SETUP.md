# Matrix Bridge Setup — WhatsApp & Instagram (mautrix)

This is the **most involved** connector to set up, but once done it's the most powerful: WhatsApp and Instagram messages reach the real you, transparently, and Sovereign filters them like any other platform.

> Most of this guide sets up **WhatsApp** (mautrix-whatsapp). **Instagram** reuses the *same* Synapse and Sovereign connector via a second bridge (mautrix-meta) — see **[Adding Instagram](#adding-instagram-mautrix-meta)** at the end, once WhatsApp works.

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

## Step 9 — Tell Sovereign to ignore your own messages (`BRIDGE_SELF_IDS`)

The bridge echoes messages **you** send back into the portal room (attributed to your own puppet). Without telling Sovereign which account is *you*, a trigger word in your *own* outgoing message would ping your phone. Add your linked account's id to `.env`:

```env
# WhatsApp = your linked number's digits (no +). Comma-separate multiple accounts.
BRIDGE_SELF_IDS=573001234567
```

Your WhatsApp id is the number you linked; it also appears in the bridge logs as `login_id=…`. (You'll add your **Instagram** id here too — see the Instagram section.) Restart the connector after changing it:

```bash
docker compose --profile whatsapp up -d connectors
```

## Step 10 — Bring up the whole stack

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

| Symptom                                                                                                                                                                                                                                                                                           | Cause / fix                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Legacy bridge config detected … migrator is not set` (crash loop)                                                                                                                                                                                                                             | You're on bridgev2 with an old config. Regenerate it (Step 3–4).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `PermissionError: /data/signing.key` (Synapse)                                                                                                                                                                                                                                                  | `synapse_data` not owned by 991. Re-run the `chown -R 991:991 /data` from Step 2.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Synapse can't read registration / appservice not loaded                                                                                                                                                                                                                                           | `registration.yaml` not world-readable. `chmod 644 mautrix/registration.yaml`, restart Synapse.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Pairing fails:`missing <link_code_pairing_wrapped_primary_ephemeral_pub>`                                                                                                                                                                                                                       | Code entered too late. Re-run Step 8 and enter the fresh code within ~60 s.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Connector idle / not forwarding                                                                                                                                                                                                                                                                   | `MATRIX_ACCESS_TOKEN` not set in `.env` (Step 7), or you started without `--profile whatsapp`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Nothing happens on the first message to a new contact                                                                                                                                                                                                                                             | Expected — send a second message (portal-creation timing).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| You get pinged by messages**you** sent                                                                                                                                                                                                                                                      | Add your account id to`BRIDGE_SELF_IDS` (Step 9) and restart the connector.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Bridge loops`M_FORBIDDEN: Application service has not registered this user (@whatsappbot:...)` / `(@metabot:...)` every ~10s after a **fresh** registration + Synapse restart, even though the as_token and namespace regex are correct                                                 | Synapse requires an AS to explicitly`POST /_matrix/client/v3/register` (type `m.login.application_service`) for a ghost user before it can masquerade as them — Synapse never auto-vivifies AS namespace users on the fly (`synapse/api/auth/base.py`: `validate_appservice_can_control_user_id` checks `store.get_user_by_id(user_id)` and 403s if absent). Unblock the bot account with one manual call: `docker compose exec -T synapse curl -s -XPOST http://localhost:8008/_matrix/client/v3/register -H 'Authorization: Bearer <as_token from registration.yaml>' -H 'Content-Type: application/json' -d '{"type":"m.login.application_service","username":"whatsappbot"}'` (swap `whatsappbot`/token for `metabot` and the meta registration's as_token for the Instagram bridge).                                                                                                                                   |
| Real messages arrive at the bridge (visible in`docker compose logs mautrix`) but never reach Sovereign — repeated `M_FORBIDDEN: Application service has not registered this user (@whatsapp_<number>:...)` / `(@meta_<id>:...)` for **many different** ghost users, not just the bot | This happens when`./mautrix/mautrix-whatsapp.db` or `./mautrix-meta/mautrix-meta.db` is **reused from a previous deployment** pointed at a *different* Synapse (e.g. this stack restored on new infrastructure with a fresh `synapse_data` volume but old bridge DBs). The bridge caches "already registered" ghost MXIDs in its own `mx_registrations` table and skips the required `/register` call for any of them — even though the *new* Synapse has never seen them. Fix: clear the stale cache so the bridge re-registers everyone against the current homeserver, then restart the bridge: `docker compose exec mautrix sqlite3 /data/mautrix-whatsapp.db 'DELETE FROM mx_registrations;'` (and the same for `mautrix-meta` / `mautrix-meta.db`), then `docker compose restart mautrix mautrix-meta`. Safe — this table is pure bookkeeping, not chat history or the WhatsApp/Instagram login session. |
| After the`mx_registrations` fix above, ghosts register fine but sends still 403 with `User @whatsapp_<number>:... not in room !<id>:sovereign.local`                                                                                                                                          | Second layer of the same restored-deployment problem: each bridge's`portal` table also caches the **Matrix room ID** per chat from the old Synapse. The ghost is now registered, but was never actually joined to that *specific* stale room under the new Synapse. Fix: clear the cached room mapping so the bridge recreates each portal fresh on next activity — `docker compose exec mautrix sqlite3 /data/mautrix-whatsapp.db "UPDATE portal SET mxid = NULL WHERE mxid IS NOT NULL;"` (and the same for `mautrix-meta`), then `docker compose restart mautrix mautrix-meta`. Portals recreate lazily, one chat at a time, only once that chat gets new activity — expect existing conversations to "come back online" gradually rather than all at once. Doesn't touch chat content or the login session.                                                                                                            |

---

## Adding Instagram (mautrix-meta)

Instagram uses **mautrix-meta**. It reuses the **same Synapse** and the **same Sovereign connector** as WhatsApp — you're just adding a second bridge. Do this after WhatsApp is working.

> ⚠️ **Image tag matters.** `dock.mau.dev/mautrix/meta:latest` (mainline) **dropped Instagram support** — it now identifies as `mautrix-facebook` and rejects `mode: instagram` at startup with `"instagram is no longer supported in this bridge"`. Instagram lives on a **separately maintained, actively built** tag on the same registry: `dock.mau.dev/mautrix/meta:ig-latest` (self-identifies as `mautrix-instagram`; no `mode` field needed since it's Instagram-only). `docker-compose.yml`'s `mautrix-meta` service is pinned to `ig-latest` for this reason — don't change it back to `:latest` or Instagram breaks again. If `ig-latest` ever disappears too, check `https://mau.dev/api/v4/projects/324/registry/repositories/98/tags?per_page=100` for current `ig-*` tags before giving up on Instagram entirely.

> ⚠️ **Risk:** mautrix-meta logs into Instagram with your **session cookies** via Instagram's unofficial API. Instagram can challenge or disable the account; there's no official API for personal DMs. Enable 2FA on the account to reduce blocks.

The `mautrix-meta` service is already defined in `docker-compose.yml` (`ig-latest` image, appservice port **29319**, bound to `./mautrix-meta`).

### 1. Generate and configure the bridge config

```bash
docker compose --profile whatsapp run --rm mautrix-meta          # writes ./mautrix-meta/config.yaml
docker compose --profile whatsapp run --rm --user root --entrypoint chown mautrix-meta -R "$(id -u):$(id -g)" /data
```

Edit `./mautrix-meta/config.yaml`. The `ig-latest` build defaults to `appservice.id: instagram`, bot username `instagrambot`, and `username_template: instagram_{{.}}` — **override all three to `meta`/`metabot`/`meta_{{.}}`**, because the Sovereign connector (`connectors/whatsapp/index.js`) hardcodes matching on the `@meta_*` prefix, not `@instagram_*`:

```yaml
database:
    type: sqlite3-fk-wal
    uri: file:/data/mautrix-meta.db?_txlock=immediate

homeserver:
    address: http://synapse:8008
    domain: sovereign.local

appservice:
    address: http://mautrix-meta:29319
    hostname: 0.0.0.0
    port: 29319

    # Override the ig-latest defaults (id: instagram / instagrambot) so ghost
    # users come out as @meta_* — that's what the connector matches on.
    id: meta
    bot:
        username: metabot

    permissions:
        "sovereign.local": user
        "@sovereign:sovereign.local": admin

bridge:
    # Also under `bridge:` further down in the generated file.
    username_template: meta_{{.}}
```

### 2. Generate the registration & wire it into Synapse

```bash
docker compose --profile whatsapp run --rm mautrix-meta          # writes ./mautrix-meta/registration.yaml
docker compose --profile whatsapp run --rm --user root --entrypoint chown mautrix-meta -R "$(id -u):$(id -g)" /data
chmod 644 mautrix-meta/registration.yaml                          # Synapse (UID 991) must read it
```

Add the meta registration to Synapse's appservice list in `synapse/homeserver.yaml`:

```yaml
app_service_config_files:
  - /data/appservices/whatsapp-registration.yaml
  - /data/appservices/meta-registration.yaml
```

The Synapse service already mounts `./mautrix-meta/registration.yaml` → `/data/appservices/meta-registration.yaml`. Copy the updated config into the Synapse volume and restart, then start the bridge:

```bash
docker compose --profile whatsapp run --rm --user root --entrypoint sh \
  -v "$(pwd)/synapse/homeserver.yaml:/seed/homeserver.yaml:ro" \
  synapse -c 'cp /seed/homeserver.yaml /data/homeserver.yaml && chown 991:991 /data/homeserver.yaml'
docker compose --profile whatsapp up -d --force-recreate synapse
docker compose --profile whatsapp up -d mautrix-meta
docker compose logs mautrix-meta | grep -i "Bridge started"
```

### 3. Log in with Instagram cookies

From a browser logged into instagram.com, open DevTools → **Application → Cookies → https://www.instagram.com** and copy the values of `sessionid`, `csrftoken`, `mid`, `ig_did`, `ds_user_id`. Submit them via the provisioning API:

```bash
SECRET=$(docker compose exec -T mautrix-meta cat /data/config.yaml | grep -E 'shared_secret:' | head -1 | awk '{print $2}')
docker compose exec -T core python3 - "$SECRET" <<'PY'
import sys, json, urllib.request, urllib.parse
sec=sys.argv[1]; uid=urllib.parse.quote('@sovereign:sovereign.local')
def call(method, path, body=None):
    url='http://mautrix-meta:29319'+path+'?user_id='+uid
    data=json.dumps(body).encode() if body is not None else (b'{}' if method=='POST' else None)
    req=urllib.request.Request(url, method=method, headers={'Authorization':'Bearer '+sec,'Content-Type':'application/json'}, data=data)
    return urllib.request.urlopen(req).read().decode()
start=json.loads(call('POST','/_matrix/provision/v3/login/start/instagram'))
lid, sid = start['login_id'], start['step_id']
cookies={"sessionid":"PASTE","csrftoken":"PASTE","mid":"PASTE","ig_did":"PASTE","ds_user_id":"PASTE"}
print(call('POST','/_matrix/provision/v3/login/step/'+lid+'/'+sid+'/cookies', cookies))
PY
```

A `"type":"complete"` response means you're logged in. (Alternative: log into Synapse as `@sovereign` with a Matrix client like Element, DM `@metabot:sovereign.local`, send `login`, and paste a "Copy as cURL" of an instagram.com `graphql` request.)

### That's it

No connector changes are needed — the Sovereign connector already forwards Instagram (`@meta_*`) puppets and routes replies back, exactly like WhatsApp. Start everything with `docker compose --profile whatsapp up -d` and Instagram DMs flow into the Vault / Decrees / Council like every other platform.

**Notes:**

- If `./mautrix-meta/mautrix-meta.db` already holds a previously-logged-in session (e.g. restoring this stack on new infrastructure, same host files but a fresh Synapse volume), the bridge may **reconnect that old session automatically** on startup — check `state_event` via the `whoami` provisioning endpoint before assuming you need to redo the cookie login in Step 3.
- **Add your Instagram id to `BRIDGE_SELF_IDS`** (the numeric id from the login line, e.g. `17842237635275588`) alongside your WhatsApp number, so DMs *you* send don't ping your own phone. Restart the connector afterward.
- Instagram contacts have **no phone number**, so to add one to your **Council** match by their bridge id (`@meta_…`) rather than a phone — easiest after they've messaged you once (you'll see them in the Chronicle).
- `cannot change members for DM` lines in the mautrix-meta log are harmless (logged when `@sovereign` joins a DM portal).
- A large first sync creates many portals at once; the connector paces its joins to stay under Synapse's rate limit.
