# PokeeChat — Pokee AI → OpenAI Compatible

**OpenAI-compatible API proxy for [Pokee AI](https://pokee.ai)** (`api.pokee.ai`).
Uses an official `pk-...` API key from the [Pokee developer console](https://console.pokee.ai/keys).

Works with Cursor, 9router, Postman, or any OpenAI Chat Completions client.

## Setup

```bash
# 1. Get a Pokee API key (https://console.pokee.ai/keys), then:
python -m pokeechat setup

# 2. Start the server
python -m pokeechat serve
```

Or configure manually in `.env`:

```
POKEECHAT_API_KEY=sk-pokeechat          # local key that gates this proxy
POKEECHAT_HOST=127.0.0.1
POKEECHAT_PORT=1993
POKEECHAT_BASE_URL=https://api.pokee.ai/v1
POKEECHAT_DEFAULT_MODEL=pokee-isaac
POKEE_API_KEY=pk-your-key-here          # your real Pokee key (shown once)
```

## Endpoints

| Endpoint                 | Description                                |
| ------------------------ | ------------------------------------------ |
| `GET /healthz`           | Liveness check                             |
| `GET /v1/models`         | List models (`pokee-isaac`)                |
| `POST /v1/chat/completions` | Chat completions (streaming + non-streaming) |

## Model aliases

The public Pokee API only serves `pokee-isaac`. Aliases like `gpt-4o`,
`claude-sonnet`, `gemini` etc. are resolved to `pokee-isaac` so generic OpenAI
clients keep working.

## Example

```bash
curl http://127.0.0.1:1993/v1/chat/completions \
  -H "Authorization: Bearer sk-pokeechat" \
  -H "Content-Type: application/json" \
  -d '{"model":"pokee-isaac","messages":[{"role":"user","content":"hello"}]}'
```
