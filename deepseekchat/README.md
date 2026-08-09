# DeepSeekChat — DeepSeek → OpenAI Compatible

**OpenAI-compatible API proxy for [DeepSeek](https://platform.deepseek.com)** (`api.deepseek.com`).
Uses an official DeepSeek API key (new accounts get 5M free tokens, valid 30 days).

Works with Cursor, 9router, Postman, or any OpenAI Chat Completions client.

## Models

| Model | Version | Context | Thinking |
| ----- | ------- | ------- | -------- |
| `deepseek-v4-flash` | DeepSeek-V4-Flash-0731 | 1M | ✓ |
| `deepseek-v4-pro` | DeepSeek-V4-Pro | 1M | ✓ |

Aliases (`deepseek-chat` → flash, `deepseek-reasoner`/`gpt-4o`/`claude-sonnet` → pro) keep generic OpenAI clients working.

## Multi-key (round-robin)

Beberapa API key didukung: pisahkan dengan koma di `deepseek.env`.
Setiap request memakai key berikutnya secara bergilir:

```
DEEPSEEK_API_KEY=sk-a1b2c3,sk-d4e5f6,sk-g7h8i9
```

## Setup

```bash
# 1. Get a DeepSeek API key (https://platform.deepseek.com → API Keys), then:
python -m deepseekchat setup

# 2. Start the server
python -m deepseekchat serve
```

Or configure manually in `.env`:

```
DEEPSEEKCHAT_API_KEY=sk-deepseekchat
DEEPSEEKCHAT_HOST=127.0.0.1
DEEPSEEKCHAT_PORT=1996
DEEPSEEKCHAT_BASE_URL=https://api.deepseek.com
DEEPSEEKCHAT_DEFAULT_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=sk-your-deepseek-key
```

## Endpoints

| Endpoint                    | Description                             |
| --------------------------- | --------------------------------------- |
| `GET /healthz`              | Liveness check                          |
| `GET /v1/models`            | List models                             |
| `POST /v1/chat/completions` | Chat completions (streaming + non-streaming) |

## Example

```bash
curl http://127.0.0.1:1996/v1/chat/completions \
  -H "Authorization: Bearer sk-deepseekchat" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hello"}]}'
```