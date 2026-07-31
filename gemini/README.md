# GeminiChat

OpenAI-compatible API proxy for [Google Gemini](https://gemini.google.com) using browser cookie authentication.

## Usage

```bash
# Interactive setup
python -m gemini setup

# Or bootstrap from cookies directly
python -m gemini init --cookies "__Secure-1PSID=..."

# Start the server
python -m gemini serve
```

## Endpoints

- `GET /healthz`
- `GET /v1/models`
- `POST /v1/chat/completions` (streaming and non-streaming)

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GEMINICHAT_API_KEY` | `sk-geminichat` | Bearer token for API auth |
| `GEMINICHAT_HOST` | `127.0.0.1` | Bind address |
| `GEMINICHAT_PORT` | `1993` | Port |
| `GEMINICHAT_ACCOUNT` | `gemini_account.json` | Account file path |
| `GEMINICHAT_DEFAULT_MODEL` | `gemini-2.0-flash` | Default model |
| `GEMINICHAT_HOME` | — | Project root (for running from any cwd) |
| `GEMINICHAT_COOKIES` | — | Full `document.cookie` string for auto-bootstrap |
