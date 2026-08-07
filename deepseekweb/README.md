# DeepSeekWeb — chat.deepseek.com → OpenAI Compatible

**OpenAI-compatible API proxy for [DeepSeek](https://chat.deepseek.com) web chat (cookie auth).**
Uses your free DeepSeek browser session (`userToken`) — **no API balance, no billing**.

## How it works

DeepSeek's public API requires paid balance, but the free web app
(`chat.deepseek.com`) lets you chat unlimited. This module reuses your browser
session token (plus optional `ds_session_id` cookie) to call the same internal
endpoint the web app uses, exposed as a standard `/v1/chat/completions` API.

> Educational / unofficial. Must comply with DeepSeek's ToS. Sessions can expire
> and the site is rate-limited; use it in moderation.

## Models

| Model | Web behavior |
| ----- | ------------ |
| `deepseek-v4-flash` | Instant mode (fast, non-thinking) |
| `deepseek-v4-pro` | Expert mode (thinking enabled) |

Aliases: `deepseek-chat` → flash, `deepseek-reasoner`/`gpt-4o`/`claude-sonnet` → pro.

## Setup

```bash
# 1. Get the token:
#    Log in at https://chat.deepseek.com
#    DevTools (F12) → Application → Local Storage → https://chat.deepseek.com
#    Copy "userToken"
python -m deepseekweb init --token "<userToken>" --ds-session-id "<optional>"

# 2. Start the server
python -m deepseekweb serve
```

Or use the wizard: `python -m deepseekweb setup`.

## Endpoints

| Endpoint                    | Description                             |
| --------------------------- | --------------------------------------- |
| `GET /healthz`              | Liveness check                          |
| `GET /v1/models`            | List models                             |
| `POST /v1/chat/completions` | Chat completions (streaming + non-streaming) |

## Requirements

The web endpoint may require solving a Proof-of-Work challenge. If requests are
rejected, install the solver deps:

```bash
pip install wasmtime numpy
```

Without them the module still runs but DeepSeek may reject completion requests.
