# ClaudeChat

OpenAI-compatible API proxy untuk [claude.ai](https://claude.ai) via browser cookies, dengan **multi-account round-robin**.

## Cara Kerja

- Ambil cookie dari browser claude.ai
- Simpan per akun ke folder `claude_accounts/cookie_1.txt`, `cookie_2.txt`, dll
- Setiap request API dipilih akun secara round-robin (bergantian)
- 5 akun = rate limit ~5x lipat

## Setup

### 1. Dapatkan Cookie

Buka https://claude.ai → login → DevTools (F12) → Network → klik request mana saja → Copy **Cookie** header.

Atau pakai ekstensi **Cookie-Editor**, export sebagai **Header String**.

### 2. Setup Akun

```bash
# Dari root project
python -m claudechat setup
```

Ketik jumlah akun, lalu paste cookie setiap akun (enter setelah setiap cookie).

**Atau langsung via CLI** (pisahkan dengan `||`):

```bash
python -m claudechat init --cookies "sessionKey=abc...||sessionKey=xyz..."
```

Hasil:
```
claude_accounts/
  cookie_1.txt   ← cookie akun 1
  cookie_2.txt   ← cookie akun 2
  cookie_3.txt   ← cookie akun 3
  ...
```

### 3. Jalankan Server

```bash
python -m claudechat serve
```

Server berjalan di `http://127.0.0.1:1998`

## Test

```bash
# Health check
curl http://127.0.0.1:1998/healthz

# List model
curl -H "Authorization: Bearer sk-claudechat" http://127.0.0.1:1998/v1/models

# Chat (streaming)
curl -X POST http://127.0.0.1:1998/v1/chat/completions \
  -H "Authorization: Bearer sk-claudechat" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4",
    "messages": [{"role": "user", "content": "Halo"}],
    "stream": true
  }'
```

## Model

| Alias | Model ID |
|-------|----------|
| `claude-sonnet-4` | `claude-sonnet-4-20250514` |
| `claude-opus-4` | `claude-opus-4-20250514` |
| `claude-haiku-4.5` | `claude-haiku-4-20250304` |
| `claude-sonnet-3.5` | `claude-sonnet-3-5-20241022` |
| `claude-opus-3.5` | `claude-3-5-opus-20250620` |
| `claude-3-opus` | `claude-3-opus-20240229` |

## Lingkungan

| Variable | Default | Keterangan |
|----------|---------|------------|
| `CLAUDE_API_KEY` | `sk-claudechat` | API key untuk akses |
| `CLAUDE_HOST` | `127.0.0.1` | Bind address |
| `CLAUDE_PORT` | `1998` | Port |
| `CLAUDE_ACCOUNT` | `claude_accounts` | Folder cookie akun |
| `CLAUDE_DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Model default |
| `CLAUDE_HOME` | - | Absolute path project |

## Catatan

- Claude.ai akun gratis punya **rate limit harian** (~20-50 pesan/akun)
- Dengan 5 akun, total ~100-250 pesan/hari sebelum limit
- Cookie bisa expired — jika dapat 403, ambil cookie baru lewat browser
- File `cookie_*.txt` berisi **raw cookie string** (bukan JSON)
