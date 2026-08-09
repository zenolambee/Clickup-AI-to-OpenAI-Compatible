# DeepSeekWeb — Panduan Instalasi Profesional

> **OpenAI-compatible API proxy untuk `chat.deepseek.com` (cookie auth).**
> Gratis — tanpa saldo API, tanpa billing. Menggunakan sesi browser kamu untuk
> mengakses model **DeepSeek-V4-Flash** (Instant Mode) dan **DeepSeek-V4-Pro**
> (Expert Mode) lewat endpoint `/v1/chat/completions` standar OpenAI.

---

## 1. Keperluan Sistem (Requirements)

| Kebutuhan | Spesifikasi |
|-----------|-------------|
| Sistem Operasi | Linux / macOS / Windows (WSL direkomendasikan) |
| Python | **3.11+** |
| Paket pip | `fastapi`, `uvicorn`, `curl_cffi`, `python-dotenv` |
| Paket PoW (opsional tapi disarankan) | `wasmtime`, `numpy` |
| Akun | Login aktif di https://chat.deepseek.com |

> **Catatan penting:** modul ini adalah solusi **non-resmi / edukasi**. Wajib
> mematuhi Terms of Service DeepSeek. Gunakan secukupnya untuk menghindari
> rate-limit atau pemblokiran sesi.

---

## 2. Instalasi

### 2.1 Clone repository

```bash
git clone https://github.com/mughu-id/Clickup-AI-to-OpenAI-Compatible.git
cd Clickup-AI-to-OpenAI-Compatible
```

### 2.2 Buat virtual environment

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (CMD)
python -m venv .venv
.venv\Scripts\activate
```

### 2.3 Install dependensi inti

```bash
pip install -r requirements.txt
pip install -e .        # mendaftarkan CLI: deepseekweb / deepseekchat
```

### 2.4 Install solver Proof-of-Work (wajib agar model Expert bisa dipakai)

Tanpa paket ini, DeepSeek akan menolak permintaan dengan
`40300 MISSING_HEADER`. Instal:

```bash
pip install wasmtime numpy
```

> `pow.wasm` sudah tersedia di dalam folder `deepseekweb/` — tidak perlu
> mengunduh apa pun secara manual.

---

## 3. Ambil Token dari Browser

1. Login di https://chat.deepseek.com
2. Tekan **F12** (DevTools)
3. Tab **Application** → **Local Storage** → `https://chat.deepseek.com`
4. Cari key **`userToken`** → salin nilainya (string panjang, contoh dimulai dengan `qT...` atau `eyJ...`)
5. (Opsional) Tab **Cookies** → salin nilai **`ds_session_id`** untuk stabilitas sesi

> **Jangan** menyalin seluruh `document.cookie` ke dalam kolom token —
> yang dibutuhkan hanya nilai `userToken` (dan opsional `ds_session_id`).

---

## 4. Konfigurasi — Tempel Saja di Env (Cara Termudah)

Cara tercepat: buka `deepseekweb.env`, tempel 2 nilai, lalu jalankan server.

### 4.1 Buka `deepseekweb.env`

```
# ← tempel userToken di bawah ini
DEEPSEEKWEB_TOKEN=qTv...
# ← tempel ds_session_id di bawah ini (opsional)
DEEPSEEK_WEB_DS_SESSION_ID=
```

### 4.2 Isi `userToken` (satu atau lebih)

1. Login di https://chat.deepseek.com
2. Tekan **F12** (DevTools)
3. Tab **Application** → **Local Storage** → `https://chat.deepseek.com`
4. Salin nilai key **`userToken`** → tempel di baris `DEEPSEEKWEB_TOKEN=`

### 4.3 Isi `ds_session_id` (opsional)

1. DevTools → **Application** → **Cookies** → `https://chat.deepseek.com`
2. Salin nilai **`ds_session_id`** → tempel di baris `DEEPSEEK_WEB_DS_SESSION_ID=`

### Multi-cookie (round-robin)

Untuk beberapa akun, pisahkan nilai dengan **koma** — pasangan tergantung urutan
(akun-1 = token-1 + session-1, akun-2 = token-2 + session-2, dst.):

```
DEEPSEEKWEB_TOKEN=tok1,tok2,tok3
DEEPSEEK_WEB_DS_SESSION_ID=sid1,sid2
```

Setiap request ke `/v1/chat/completions` memakai akun berikutnya (round-robin),
menyebar beban dan mengurangi risiko rate-limit.

> Kedua nilai itu **langsung terbaca** saat server start — tidak perlu menjalankan
> `init` atau menulis file akun. `deepseek_account.json` otomatis dibuat ulang.

### 4.4 (Alternatif) Wizard interaktif

```bash
python -m deepseekweb setup
```

Prompt akan meminta token + `ds_session_id` (bisa dikosongkan). Hasilnya ditulis
ke `deepseekweb.env` dan `deepseek_account.json`.

### 4.5 (Alternatif) CLI langsung

```bash
python -m deepseekweb init \
  --token "<userToken-dari-localStorage>" \
  --ds-session-id "<opsional>" \
  --account deepseek_account.json
```

| Variabel | Deskripsi |
|----------|-----------|
| `DEEPSEEKWEB_API_KEY` | Bearer token lokal untuk akses ke proxy ini |
| `DEEPSEEKWEB_HOST` | Bind host (default `127.0.0.1`) |
| `DEEPSEEKWEB_PORT` | Port (default `1997`) |
| `DEEPSEEKWEB_ACCOUNT` | Path file akun JSON |
| `DEEPSEEKWEB_BASE_URL` | Endpoint internal web DeepSeek |
| `DEEPSEEKWEB_DEFAULT_MODEL` | Model default |
| `DEEPSEEKWEB_TOKEN` | **Wajib** — userToken dari localStorage, tinggal tempel di sini |
| `DEEPSEEK_WEB_DS_SESSION_ID` | Opsional — nilai cookie `ds_session_id` |

> **Keamanan:** `deepseek_account.json` dan `deepseekweb.env` berisi kredensial
> sesi. Keduanya sudah ada di `.gitignore` — jangan pernah commit.

---

## 5. Menjalankan Server

```bash
# dari folder proyek (venv aktif)
python -m deepseekweb serve
```

atau lewat launcher `scripts/` (bisa dari direktori mana pun):

```bash
export PATH="$PWD/scripts:$PATH"   # Linux / macOS
deepseekweb serve
```

Server akan mendengarkan di: **http://127.0.0.1:1997**

### Menjalankan sebagai daemon (Linux)

```bash
nohup python -m deepseekweb serve >/tmp/deepseekweb.log 2>&1 </dev/null &
```

### Menjalankan dengan PM2 (opsional, auto-restart)

```bash
npm install -g pm2
pm2 start ecosystem.config.cjs --only deepseekweb
pm2 status
pm2 logs deepseekweb
```

---

## 6. Uji Coba (Test)

### Health check

```bash
curl http://127.0.0.1:1997/healthz
# {"status":"ok"}
```

### Daftar model

```bash
curl http://127.0.0.1:1997/v1/models \
  -H "Authorization: Bearer sk-deepseekweb"
```

### Chat completion — non-streaming

```bash
curl http://127.0.0.1:1997/v1/chat/completions \
  -H "Authorization: Bearer sk-deepseekweb" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-pro","messages":[{"role":"user","content":"Halo, jawab singkat"}]}'
```

### Chat completion — streaming

```bash
curl -N http://127.0.0.1:1997/v1/chat/completions \
  -H "Authorization: Bearer sk-deepseekweb" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","stream":true,"messages":[{"role":"user","content":"Halo"}]}'
```

### Integrasi dengan klien OpenAI standar

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:1997/v1", api_key="sk-deepseekweb")

resp = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[{"role": "user", "content": "Halo"}],
)
print(resp.choices[0].message.content)
```

---

## 7. Model & Alias

| Model | Mode Web | Keterangan |
|-------|----------|------------|
| `deepseek-v4-flash` | Instant | Cepat, non-thinking |
| `deepseek-v4-pro` | Expert | Lebih kuat, thinking enabled |

Alias yang didukung:

| Alias | Dipetakan ke |
|-------|--------------|
| `deepseek`, `deepseek-chat`, `deepseek-v3` | `deepseek-v4-flash` |
| `deepseek-reasoner`, `deepseek-r1` | `deepseek-v4-pro` |
| `gpt`, `gpt-4o`, `claude`, `claude-sonnet`, `claude-opus` | `deepseek-v4-pro` |

---

## 8. Struktur Proyek

```
deepseekweb/
├── __main__.py      # CLI: serve / init / setup
├── config.py        # Load konfigurasi dari deepseekweb.env / .env
├── account.py       # DeepSeekWebAccount, headers (x-client-version 2.0.0)
├── client.py        # Klien chat.deepseek.com (session, PoW, streaming)
├── openai_api.py    # FastAPI → endpoint OpenAI-compatible
├── models.py        # Daftar model + alias resolver
├── pow.py           # Solver Proof-of-Work
├── pow.wasm         # WASM solver (sudah disertakan)
└── README.md        # Ringkasan
```

---

## 9. Troubleshooting

| Gejala | Penyebab & Solusi |
|--------|-------------------|
| `40300 MISSING_HEADER` | Solver PoW belum terpasang → `pip install wasmtime numpy`, restart server |
| `401` / token tidak valid | Token kadaluarsa → ambil ulang `userToken` dari localStorage |
| `Update to the latest version to use Expert` | Header `x-client-version` hilang → pastikan kode terbaru (v2.0.0 di `account.py`) |
| Balasan kosong pada model Pro | Mode Expert lebih lambat; tunggu sampai selesai, atau coba streaming |
| `500 Missing DEEPSEEKWEB_TOKEN` | Akun/env belum dikonfigurasi → jalankan `python -m deepseekweb setup` |
| Rate-limited / sering gagal | Gunakan secukupnya; DeepSeek web menerapkan batas pemakaian |
| Server tidak bisa diakses | Periksa `DEEPSEEKWEB_HOST` / `DEEPSEEKWEB_PORT`; pastikan firewall terbuka |

---

## 10. Keamanan

- Server default mengikat `127.0.0.1` — jangan buka ke internet tanpa TLS dan autentikasi.
- Jangan pernah mempublikasikan `deepseek_account.json`, `deepseekweb.env`, atau log yang mengandung token.
- Token adalah akses penuh ke akun chat.deepseek.com kamu — perlakukan seperti kata sandi.

---

## 11. Batasan

- **Tidak resmi** — DeepSeek dapat mengubah endpoint/format kapan saja.
- Sesi bisa kedaluwarsa; token perlu di-refresh dari browser.
- Ada rate-limit sisi situs.
- Bukan untuk konteks multi-instance pada token yang sama secara bersamaan.

## Lisensi

[MIT](../LICENSE)
