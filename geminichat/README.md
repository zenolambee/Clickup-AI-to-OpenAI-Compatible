# GeminiChat — OpenAI-compatible proxy for Google Gemini

Unofficial OpenAI-compatible proxy that routes chat to **Google Gemini** models
using your **browser session** from AI Studio (aistudio.google.com), mirroring the
pattern of `qwenchat` / `boltchat` / `notionchat` in this repo.

> **Important: session, not an "API key".** Capturing the cookie gives you a
> **Google session** (incl. SAPISID), which this proxy uses to call Gemini's
> internal endpoint. An API key **cannot** be extracted from cookies — real Gemini
> API keys are created only at https://aistudio.google.com/apikey. Here the "API
> key" you receive is a *local* key (`sk-geminichat-...`) that protects your own
> server.

> **Status: experimental scaffold.** Gemini's internal endpoint is undocumented
> and may change. The HTTP/OpenAI surface is complete and functional; the
> streaming transport in `client.py` is marked with `REVIEW` and must be validated
> against the live site (DevTools → Network) before it will stream real answers.

## Cara pakai (ringkas)

```bash
# 1. buat venv & install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .

# 2. ambil cookie dari browser
#    buka https://aistudio.google.com → login → F12 → Application → Cookies
#    → copy document.cookie

# 3. setup (tempel cookie saat diminta)
geminichat setup

# 4. jalankan server
geminichat serve
```

## Run

```bash
geminichat serve
```

```bash
# health check
curl http://127.0.0.1:1997/healthz

# daftar model
curl http://127.0.0.1:1997/v1/models -H "Authorization: Bearer sk-geminichat-..."

# panggil chat (non-streaming)
curl http://127.0.0.1:1997/v1/chat/completions \
  -H "Authorization: Bearer sk-geminichat-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-2.5-flash","messages":[{"role":"user","content":"hi"}]}'

# streaming
curl -N http://127.0.0.1:1997/v1/chat/completions \
  -H "Authorization: Bearer sk-geminichat-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-2.5-flash","stream":true,"messages":[{"role":"user","content":"hi"}]}'
```

Base URL untuk klien OpenAI-compatible: `http://127.0.0.1:1997/v1`

## Models

| Model id             | Notes                 |
|----------------------|-----------------------|
| `gemini-3-pro`       | Latest pro            |
| `gemini-3-flash`     | Latest flash          |
| `gemini-2.5-pro`     | 2.5 pro               |
| `gemini-2.5-flash`   | Default (recommended) |
| `gemini-2.5-flash-lite` | Lite flash         |

Bolt-routing note: whether a model is actually accessible depends on what your
Google account is allowed to use.

## Config reference

| Env var                    | Default                                            | Description                    |
|----------------------------|----------------------------------------------------|--------------------------------|
| `GEMINICHAT_API_KEY`       | `sk-geminichat`                                    | Local API key clients send     |
| `GEMINICHAT_HOST`          | `127.0.0.1`                                        | Bind host                      |
| `GEMINICHAT_PORT`          | `1997`                                             | Port                           |
| `GEMINICHAT_ACCOUNT`       | `gemini_account.json`                              | Account file                   |
| `GEMINICHAT_COOKIE`        | *(empty)*                                          | Cookie from aistudio.google.com |
| `GEMINICHAT_SAPISID`       | *(empty)*                                          | SAPISID token                  |
| `GEMINICHAT_BASE_URL`      | `https://aistudio.google.com`                      | Web base URL                   |
| `GEMINICHAT_API_BASE_URL`  | `https://generativelanguage.googleapis.com`        | Gemini API base URL            |
| `GEMINICHAT_DEFAULT_MODEL` | `gemini-2.5-flash`                                 | Default model                  |

## Troubleshooting streaming

If `/v1/chat/completions` returns no text, open DevTools → Network on AI Studio,
capture a generateContent request, and update the `REVIEW`-marked sections in
`geminichat/client.py` (Authorization header + response framing) to match the live
protocol.

> **Legal note:** This is unofficial/educational. Comply with Google's Terms of
> Service and your plan limits. Using a session outside Google's intended UI may
> violate ToS.
