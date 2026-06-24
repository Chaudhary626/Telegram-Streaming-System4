# Telegram Video Streaming System

A platform that stores videos on Telegram channels and streams them on a
website via MTProto (Pyrogram) with no 20MB limit (up to 4GB), with an admin
panel, subadmin system, manual payment workflow, and a custom multi-audio /
multi-quality HTML5 player.

## Architecture

1. **Telegram Bot** — content management + user interaction
2. **Stream Server** — MTProto-based streaming (no file size limit)
3. **MySQL Database** — stores all data
4. **Web Panel** — Admin + Subadmin dashboards
5. **Website Player** — video playback

## Build phases

- [x] **Phase 1** — Project structure, DB schema, config, DB layer, Docker
- [x] **Phase 2** — Stream server (Pyrogram MTProto + HTTP range requests)
- [x] **Phase 3** — Telegram bot (content hierarchy, uploads, /myvideos, /links)
- [x] **Phase 4** — Web backend (auth, admin panel, subadmin panel, subscriptions, payments)
- [x] **Phase 5** — Player + website (watch/embed, multi-audio/quality, password mgmt)
- [x] **Phase 6** — Subscription enforcement (plan limits + expiry handling)

## Phase 6 — Subscription enforcement

`app/services/subscription.py` is the single source of truth for what a user
may currently do:

- **Expiry handling:** if `plan_expires_at` is in the past (or no plan is set),
  the user is treated as the **Free** plan — `get_effective_plan()` downgrades
  automatically, so premium limits/features no longer apply.
- **Upload limits:** `can_upload()` blocks a new video once `count >=`
  `Plan.max_videos` (`0` = unlimited). Enforced in the **bot** upload flow
  *before* anything is stored in the channel, and surfaced in the **panel**
  (usage banner + plan card showing used/limit, expiry, and an expired notice).

## Phase 5 — Player & website

Public player pages backed by token-gated MTProto streams.

- **`/watch/{slug}`** — full page with the custom HTML5 player.
- **`/embed/{slug}`** — chromeless version for `<iframe>` embedding.
- **Custom player** (`app/web/static/player.js` + `player.css`): independent
  **Audio (language)** and **Quality** selectors. Switching either axis is
  *seamless* — the current timestamp and play/pause state are captured, the
  `<video>` source is swapped, and playback resumes at the same position.
  Changing quality keeps the language; changing language keeps the quality
  (when available).
- Each source gets a freshly minted, expiring **stream token** in the player
  payload (`app/services/player.py`), so the public pages never expose a
  permanent stream URL.

### Password management (panel login for bot users)

- **Bot:** `/setpassword <new password>` (or interactive) sets the user's web
  panel password and replies with their panel username.
- **Admin:** the Users page has a *Set password* action to set/reset any
  subadmin's password.
- Shared logic in `app/services/password.py` (min 6 chars).

## Phase 4 — Web panels

FastAPI + Jinja2 panels with cookie-session auth (signed HttpOnly JWT).

- **Login/logout:** `/login`, `/logout`.
- **Admin panel:** mounted at `/admin/{ADMIN_SECRET_PATH}` (secret URL) **and**
  guarded by an admin session (defense in depth; wrong secret returns 404).
  Pages: dashboard, users (create subadmin, enable/disable, assign/extend
  plans), plans, payment methods, payment review (approve/reject → activates
  plan), audit logs.
- **Subadmin panel:** `/panel` — own content + sources + watch/embed links only
  (owner-scoped), plus `/panel/plans` to view plans, see configured payment
  methods, submit a payment request, and track its status.

Log in as the bootstrap admin (`ADMIN_USERNAME` / `ADMIN_PASSWORD`); you are
redirected to the secret admin path automatically.

## Phase 3 — Telegram bot

A Pyrogram bot (separate client from the streamer, both run in the app
lifespan) for content management with strict per-user isolation.

**Commands**

- `/start` — inline-button main menu
- `/new Name` or `/new Movie/Season 1/Episode 1` — create content / full path
- `/subnew` — add nested content interactively
- `/myvideos` — browse your content tree
- `/links` — list your player links

**Uploads:** open a content item → *Upload Here* → send a video. The bot copies
it into `STORAGE_CHANNEL_ID` and stores `file_id`, `file_unique_id`,
`file_size`, `channel_id`, `message_id`, plus detected `language`/`quality`
(from the filename, e.g. `movie_hindi_720p.mp4`) into `video_sources`.

**Isolation:** each Telegram user maps to one subadmin `User` row
(`telegram_id`); all reads/writes are scoped by `owner_id`, so a subadmin only
ever sees their own content.

**Modules:** `app/bot/client.py` (bot client), `app/bot/handlers.py`
(commands/callbacks/media), `app/bot/keyboards.py` (inline UI),
`app/bot/state.py` (per-user state), `app/services/content.py` (shared,
owner-scoped DB logic).

## Phase 2 — MTProto streaming

The stream server reads video bytes directly from Telegram via MTProto
(Pyrogram), bypassing the Bot API `getFile` 20 MB limit and supporting files up
to 4 GB. It speaks HTTP range requests so browsers and players can seek.

**Key modules**

- `app/telegram/client.py` — shared, lazily-started Pyrogram bot client
- `app/telegram/streamer.py` — 1 MiB chunk-aligned range reader over
  `stream_media`
- `app/telegram/resolver.py` — resolves a `VideoSource` to a current `file_id`
- `app/core/ranges.py` — `Range: bytes=...` header parser
- `app/api/stream.py` — `GET /stream/{source_id}?token=...`

**Testing the stream (development)**

```bash
# 1. Mint a token (dev only; disabled when ENV=production)
curl localhost:8000/stream-token/1
# 2. Request a byte range
curl -H "Range: bytes=0-1048575" -D - \
     "http://localhost:8000/stream/1?token=..." -o /dev/null
# Expect: 206 Partial Content, Content-Range: bytes 0-1048575/<size>
```

## Project layout

```
app/
  config.py          # env-based settings
  main.py            # FastAPI entrypoint
  core/security.py   # password hashing + tokens
  db/
    base.py          # async engine, session, declarative base
    models.py        # ORM models
    init_db.py       # create tables, seed plans + admin
db/schema.sql        # raw MySQL schema (used by docker entrypoint)
Dockerfile
docker-compose.yml
requirements.txt
```

## Local (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.db.init_db        # create tables + seed (needs running MySQL)
uvicorn app.main:app --reload
```
