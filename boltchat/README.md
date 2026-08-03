# BoltChat — OpenAI-compatible proxy for Bolt.new

Unofficial OpenAI-compatible proxy that aims to route chat to **Bolt.new's** AI
models using your **browser session** (cookie / StackBlitz session token), mirroring
the pattern of `notionchat` and `qwenchat` in this repo.

> **Status: experimental scaffold.** Bolt.new's AI backend is **proprietary and
> private**, and its chat transport is WebSocket/Socket based (WebContainers-style),
> **not** a plain REST `chat completions` endpoint like Notion/Qwen. The HTTP/OpenAI
> surface below is complete and functional; the streaming transport in `client.py`
> targets the *publicly documented* StackBlitz relay framing but still needs to be
> **validated against the live site** (marked with `REVIEW` in the code) before it
> will stream real answers.

---

## Important clarification: session, not "API key"

Bolt.new does **not** put an *API key* in its cookies. It authenticates the web app
with a **StackBlitz login session**. That session is what grants access to the AI
models Bolt routes to (Claude / Gemini family) and determines your quotas.

So this proxy takes a **session** — not an OpenAI API key — and exposes it as an
OpenAI-compatible endpoint for clients like Cursor, 9router, or Postman.

## Features

- OpenAI-compatible endpoints: `GET /v1/models`, `POST /v1/chat/completions` (stream & non-stream)
- API-key protection for your local server (`BOLTCHAT_API_KEY`)
- Session captured from cookie (`document.cookie`) or `sb_session` token
- WebSocket relay transport with `websockets`; falls back to HTTP validation

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
```

## Get your Bolt session

1. Open https://bolt.new and log in.
2. DevTools (F12) → Application → Cookies → `https://bolt.new`
3. Copy the full `document.cookie` string.

## Setup

```bash
boltchat setup
```

This validates & saves `bolt_account.json`, then writes `.env` with:

```ini
BOLTCHAT_API_KEY=sk-boltchat-...
BOLTCHAT_HOST=127.0.0.1
BOLTCHAT_PORT=1996
BOLTCHAT_ACCOUNT=bolt_account.json
BOLTCHAT_COOKIE=<your cookie>
```

## Cara pakai (ringkas)

```bash
# 1. buat venv & install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .

# 2. ambil cookie dari browser
#    buka https://bolt.new → login → F12 → Application → Cookies → copy document.cookie

# 3. setup (tempel cookie saat diminta)
boltchat setup

# 4. jalankan server
boltchat serve
```

## Run

```bash
boltchat serve
```

```bash
# health check
curl http://127.0.0.1:1996/healthz

# daftar model
curl http://127.0.0.1:1996/v1/models -H "Authorization: Bearer sk-boltchat-..."

# panggil chat (non-streaming)
curl http://127.0.0.1:1996/v1/chat/completions \
  -H "Authorization: Bearer sk-boltchat-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"bolt-agent","messages":[{"role":"user","content":"hi"}]}'

# streaming
curl -N http://127.0.0.1:1996/v1/chat/completions \
  -H "Authorization: Bearer sk-boltchat-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"bolt-agent","stream":true,"messages":[{"role":"user","content":"hi"}]}'
```

Base URL untuk klien OpenAI-compatible: `http://127.0.0.1:1996/v1`

## Models

Bolt routes automatically per task; it does not publish a stable model list. The
proxy exposes these tiers as labels (resolved server-side):

| Model id     | Notes                          |
|--------------|--------------------------------|
| `bolt-agent` | Default / Standard (recommended) |
| `bolt-pro`   | Pro tier                       |
| `bolt-max`   | Max tier                       |

## Config reference

| Env var                 | Default                                | Description                        |
|-------------------------|----------------------------------------|------------------------------------|
| `BOLTCHAT_API_KEY`      | `sk-boltchat`                          | API key clients must send          |
| `BOLTCHAT_HOST`         | `127.0.0.1`                            | Bind host                          |
| `BOLTCHAT_PORT`         | `1996`                                 | Port                               |
| `BOLTCHAT_ACCOUNT`      | `bolt_account.json`                    | Account file                       |
| `BOLTCHAT_COOKIE`       | *(empty)*                              | Browser cookie from bolt.new       |
| `BOLTCHAT_SESSION_TOKEN`| *(empty)*                              | StackBlitz session token           |
| `BOLTCHAT_BASE_URL`     | `https://bolt.new`                     | Web base URL                       |
| `BOLTCHAT_DEFAULT_MODEL`| `bolt-agent`                           | Default model                      |
| `BOLTCHAT_WS_URL`       | `wss://bolt.new/.well-known/ai/relay`  | WebSocket relay endpoint           |

## Troubleshooting streaming

Bolt's internal message schema is undocumented and changes. If `/v1/chat/completions`
returns no text, open DevTools → Network → WS on bolt.new, capture a real request,
then update the `REVIEW`-marked sections in `boltchat/client.py` (request envelope
and frame parsing) to match the live protocol, and adjust `BOLTCHAT_WS_URL` if needed.

> **Legal note:** This is unofficial/educational. You must comply with StackBlitz's
> Terms of Service and your plan's usage limits. Using a session outside Bolt's
> intended UI may violate ToS.
