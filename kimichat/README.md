<div align="center">

# Kimi AI → OpenAI Compatible

**Proxy tidak resmi berbasis OpenAI API untuk Kimi (kimi.com / Moonshot)**
Autentikasi via cookie/token · streaming · Cursor / Postman / 9router

</div>

---

> **Edukasi / tidak resmi** — hanya untuk belajar dan riset. Tidak berafiliasi dengan Kimi/Moonshot. Anda wajib mematuhi Terms of Service Kimi dan batas paket akun Anda.

`kimichat` adalah server HTTP kompatibel-OpenAI yang meneruskan chat ke **API web internal Kimi** (`kimi.com`) memakai sesi browser Anda (`refresh_token`). Cocok dipakai dengan [Cursor](https://cursor.com), Postman, atau klien OpenAI Chat Completions apa pun.

Paket ini adalah adaptasi dari pola `qwenchat` di repo ini, disesuaikan untuk skema autentikasi dua-token milik Kimi.

## Fitur

- **Endpoint kompatibel-OpenAI**
  - `POST /v1/chat/completions` (streaming & non-streaming)
  - `GET /v1/models`
  - `GET /healthz`
- **Autentikasi cookie/token browser** — tidak perlu API key resmi berbayar
- **Auto-refresh token** — `refresh_token` ditukar otomatis menjadi `access_token` (dan diperbarui saat 401)
- **Alias model** — mis. `kimi`, `k1.5`, `k2` dipetakan ke ID internal Kimi

## Cara kerja

```
Klien (Cursor / Postman / 9router)
        │
        ▼
   KimiChat (FastAPI)  ──  refresh_token → access_token
        │  pesan OpenAI → payload chat Kimi
        ▼
   Kimi Web API  POST /api/chat/{id}/completion/stream
        │  aliran SSE (event: cmpl)
        ▼
   KimiChat parse → chat.completion OpenAI
```

## Skema autentikasi Kimi (penting)

Kimi memakai **dua token**:

| Token | Sumber | Umur | Kegunaan |
|-------|--------|------|----------|
| `refresh_token` | Local Storage `kimi.com` (key `refresh_token`) | panjang | ditukar jadi access_token |
| `access_token` | hasil `GET /api/auth/token/refresh` | pendek | Bearer untuk tiap request |

Anda **cukup mengisi `refresh_token`** — `access_token` dibuat otomatis.

## Persyaratan

- Python 3.11+
- Akun Kimi yang aktif (batas paket berlaku)
- `refresh_token` dari sesi browser kimi.com

## Instalasi

Dari **root repo** (`Clickup-AI-to-OpenAI-Compatible/`), bukan dari folder `kimichat/`:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

`pip install -e .` mendaftarkan perintah CLI: **`kimichat`** dan **`kimi`** (perilaku sama). Atau jalankan langsung sebagai modul: `python -m kimichat`.

## Konfigurasi environment

Salin contoh env ke root repo lalu isi token:

```bash
# dari root repo
cp kimichat/.env.example .env
```

Variabel di `.env`:

| Variabel | Deskripsi |
|----------|-----------|
| `KIMICHAT_API_KEY` | Bearer token yang harus dikirim klien (`Authorization: Bearer ...`) |
| `KIMICHAT_HOST` | Host bind (default `127.0.0.1`) |
| `KIMICHAT_PORT` | Port (default `1997`) |
| `KIMICHAT_ACCOUNT` | Path file akun JSON (default `kimi_account.json`) |
| `KIMICHAT_DEFAULT_MODEL` | Model default (default `kimi`) |
| `KIMICHAT_BASE_URL` | Base URL Kimi (default `https://www.kimi.com`) |
| `KIMICHAT_REFRESH_TOKEN` | **Wajib** — refresh_token dari Local Storage kimi.com |
| `KIMICHAT_ACCESS_TOKEN` | Opsional — access_token siap pakai (skip refresh pertama) |
| `KIMICHAT_COOKIES` | Opsional — `document.cookie` penuh (bantu bila ada device check) |
| `KIMICHAT_DEVICE_ID` | Opsional — device id stabil untuk header fingerprint (auto bila kosong) |
| `KIMICHAT_HOME` | Opsional — path absolut folder repo agar `.env` ditemukan dari cwd mana pun |

## Mengambil refresh_token dari browser

1. Buka [https://www.kimi.com](https://www.kimi.com) dan login.
2. Buka DevTools (F12) → **Application** → **Local Storage** → `https://www.kimi.com`.
3. Salin **value** dari key `refresh_token` (JWT panjang berawalan `eyJ...`).

Lalu bootstrap akun (validasi + simpan `kimi_account.json`):

```bash
kimichat init --refresh-token "eyJ..."
```

Atau lewat wizard interaktif (juga menulis `.env`):

```bash
kimichat setup
```

`kimichat setup` juga menerima **cookie string penuh** dan mencoba mengekstrak `refresh_token` darinya.

## Menjalankan server

```bash
kimichat serve
```

Sama dengan `python -m kimichat serve`. URL server: `http://127.0.0.1:1997` (atau sesuai `KIMICHAT_HOST` / `KIMICHAT_PORT`).

## Menguji

```bash
curl http://127.0.0.1:1997/healthz

curl http://127.0.0.1:1997/v1/models \
  -H "Authorization: Bearer sk-kimichat"

curl http://127.0.0.1:1997/v1/chat/completions \
  -H "Authorization: Bearer sk-kimichat" \
  -H "Content-Type: application/json" \
  -d '{"model":"kimi","messages":[{"role":"user","content":"Halo, perkenalkan dirimu satu kalimat."}]}'
```

Streaming (SSE):

```bash
curl -N http://127.0.0.1:1997/v1/chat/completions \
  -H "Authorization: Bearer sk-kimichat" \
  -H "Content-Type: application/json" \
  -d '{"model":"kimi","stream":true,"messages":[{"role":"user","content":"Hitung 1 sampai 5."}]}'
```

## Setup Cursor / 9router

1. Jalankan server (`kimichat serve`).
2. Di setelan custom model:
   - **Base URL:** `http://127.0.0.1:1997/v1`
   - **API key:** nilai `KIMICHAT_API_KEY` dari `.env`
   - **Model:** `kimi` (lihat `GET /v1/models`)

## Model

| Alias | Dipetakan ke |
|-------|--------------|
| `kimi`, `moonshot`, `k2`, `kimi-k2` | `kimi` |
| `k1.5`, `kimi-k1.5`, `k1.5-thinking`, `kimi-thinking` | `k1.5` |

## Perintah CLI

```bash
kimichat setup                          # wizard: token -> account.json -> .env
kimichat init --refresh-token "eyJ..."  # simpan kimi_account.json saja
kimichat init --refresh-token -         # baca token dari stdin
kimichat serve                          # jalankan API server
```

## Struktur paket

```
kimichat/
├── __init__.py       # metadata paket
├── exceptions.py     # KimiChatError
├── account.py        # KimiAccount, parse cookie, build header auth
├── config.py         # muat Settings + kredensial dari .env
├── bootstrap.py      # refresh_token -> access_token, ambil user info
├── models.py         # alias & daftar model
├── client.py         # buat chat + parse aliran SSE Kimi
├── openai_api.py     # endpoint FastAPI kompatibel-OpenAI
├── setup_cli.py      # wizard interaktif
├── __main__.py       # entry CLI (serve / setup / init)
└── .env.example      # template environment
```

## Menjalankan dengan PM2 (opsional)

`ecosystem.config.cjs` di root repo saat ini dikonfigurasi untuk `qwenchat`. Untuk menjalankan `kimichat` via PM2, ubah `name` dan `args` menjadi `-m kimichat serve`, atau jalankan langsung:

```bash
pm2 start ".venv/bin/python" --name kimichat -- -m kimichat serve
pm2 logs kimichat
```

## Catatan & keterbatasan

- **Belum diuji ke server Kimi live.** Endpoint web internal Kimi (`/api/chat`, `/api/chat/{id}/completion/stream`, event SSE `cmpl`/`all_done`, header device seperti `x-msh-device-id`) disusun berdasarkan pola reverse-engineering Kimi yang umum. Bagian yang paling mungkin perlu penyesuaian ada di `client.py` (nama field payload, tipe event) dan `bootstrap.py` (bentuk respons endpoint refresh). Sesuaikan setelah melihat respons asli dari akun Anda.
- **Kadaluarsa token** — segarkan `refresh_token` bila muncul error 401/403.
- **API tidak resmi** — Kimi dapat mengubah endpoint/format sewaktu-waktu.
- **Rate limit / kuota** — mengikuti paket akun Kimi Anda.

## Keamanan

- Jangan commit `.env`, `kimi_account.json`, atau token apa pun.
- `refresh_token` memberi akses penuh ke akun — jalankan **lokal** dan jangan diekspos ke internet publik tanpa auth + TLS.
- Bind default `127.0.0.1`. Gunakan `KIMICHAT_API_KEY` yang kuat bila server dapat dijangkau di jaringan Anda.

## Lisensi

Mengikuti lisensi repo induk: [MIT](../LICENSE).
