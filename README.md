# 🤖 Personal AI Agent (`aiagentgres`)

Personal AI Agent berbasis Telegram + Groq AI (Llama 3.3 70B). Terinspirasi
dari [Hermes Agent](https://hermes-agent.nousresearch.com/) by Nous Research
(open-source self-improving AI agent — open-claw style).

> **Status:** Phase 0 (security + refactor) — bot udah bisa di-deploy ke
> production tanpa risiko shell injection. Fitur lanjutan (multi-platform
> gateway, MCP, delegation) ada di Phase 1+ roadmap.

---

## 📁 Struktur Project

```
aiagentgres/
├── main.py              # Telegram entry point (allow-list, callback router)
├── agent.py             # Core agent loop + action handlers
├── config.py            # Env loader
├── auth.py              # OWNER allow-list + dangerous-cmd approval
├── paths.py             # Path resolution (JAGRESMAN_HOME override)
├── logging_setup.py     # Logging config
├── memory.py            # SQLite persistent memory
├── skill_loader.py      # Load skills dari folder skills/
├── skill_executor.py    # Eksekusi kode dari skill
├── skill_writer.py      # Self-improving — nulis skill sendiri via LLM
├── morning_briefing.py  # Generator briefing pagi (jadwal cron jam 07:00 WIB)
├── auto_trader.py       # Auto-trader Binance Futures (separate process)
├── webhook_server.py    # TradingView webhook listener
├── backtest*.py         # Backtest scripts
├── knowledge.txt        # Fakta personal user (legacy, akan dipisah di Phase 1)
├── AGENTS.md            # Project context (Hermes-style)
├── SOUL.md              # Personality (Hermes-style)
├── pyproject.toml       # Project metadata + dep list
├── requirements.txt     # Pinned dependency versions
├── .env.example         # Env var template
├── .gitignore           # Hardening biar gak commit secret lagi
├── tests/               # Pytest test suite
│   ├── test_smoke.py
│   └── test_auth.py
└── .github/workflows/   # GitHub Actions CI (ruff + pytest)
```

> **Catatan path:** Default `BASE_DIR` = direktori repo. Override pakai env
> var `JAGRESMAN_HOME` kalau lo butuh deploy di luar VPS produksi
> (`/root/aiagent/` udah gak hardcoded lagi).

---

## ⚙️ Setup

### 1. Clone & install
```bash
git clone https://github.com/jagres0039/aiagentgres.git
cd aiagentgres
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### 2. Setup `.env`
```bash
cp .env.example .env
# Edit .env, isi setidaknya TELEGRAM_BOT_TOKEN, GROQ_API_KEY, OWNER_TELEGRAM_IDS
```

### 3. Setup `OWNER_TELEGRAM_IDS` (WAJIB)
Cari user ID lo dengan chat ke `@userinfobot` di Telegram. Lalu set:
```
OWNER_TELEGRAM_IDS=123456789
```
Multi-owner: `OWNER_TELEGRAM_IDS=123,456,789`. **Kalau env ini kosong, bot
bakal reject semua pesan**.

### 4. (Optional) Setup `knowledge.txt`
```
=== TENTANG PEMILIK AGENT ===
Nama: [nama lo]
Kota: Bandung, Indonesia
Timezone: WIB (UTC+7)
```

Untuk personality dan project context, edit `SOUL.md` dan `AGENTS.md`.

### 5. Jalanin bot
```bash
python3.11 main.py
```

---

## 🔒 Security Model (Phase 0)

### Allow-list
Setiap handler Telegram di `main.py` dibungkus `@require_owner`. User yang
gak ada di `OWNER_TELEGRAM_IDS` di-reject sebelum agent dipanggil. Sebelum
Phase 0, hanya `EXECUTE_BASH` yang punya owner check di dalam agent.py — tapi
action lain (SKILL, SCREENSHOT, AUTO_*) bisa ditrigger LLM dari pesan user
sembarangan. Sekarang gak bisa.

### Dangerous-command approval
Setiap LLM-output `EXECUTE_BASH: ...` lewat classifier (lihat `auth.py`):

| Risk | Behavior |
|---|---|
| `safe` (ls, df, free, uptime, ...) | Auto-run kalau `AUTO_APPROVE_SAFE_COMMANDS=true` (default) |
| `moderate` (git push, pip install, kill, ...) | Tombol Approve/Skip di Telegram |
| `dangerous` (rm -rf, sudo, curl \| bash, ...) | Tombol Approve/Skip di Telegram |

Approval lewat tombol di Telegram dengan `InlineKeyboardButton`. Pending
approval timeout di 10 menit. Cross-user attack diblok — user lain gak bisa
nge-approve command yang di-trigger user A.

`EDIT_FILE` di-disable sementara di Phase 0 sampai approval flow buat
file-write selesai (Phase 1).

### File hygiene
`.env`, `*.db`, `*.log`, `service_account.json`, `playwright_cookies.json`,
`tmp_*.py`, `__pycache__/` semua di-ignore dari git. Kalau lo upgrade dari
versi sebelum Phase 0, **jangan force-push** — file lama di history-nya udah
gua hapus dari latest commit, tapi history-nya tetep ada (lo perlu revoke
session Twitter/X manual kalau pernah commit cookie).

---

## 🧪 Test & Lint

```bash
pip install -e ".[dev]"        # install ruff + pytest
ruff check .                   # lint
pytest                         # unit tests
```

CI otomatis jalanin keduanya di GitHub Actions tiap push & PR (`.github/workflows/ci.yml`).

---

## 💬 Cara Pakai

### Commands
```
/start    - Halo
/clear    - Hapus history chat
/memory   - Lihat semua memory tersimpan
/briefing - Trigger morning briefing manual
/mode     - Switch trading mode (scalping / swing)
```

### Contoh perintah natural
```
"cariin info terbaru soal Bitcoin"
"buat event meeting besok jam 10 sampai jam 11"
"cek inbox gua"
"berapa harga BTC sekarang?"
"buatin skill buat cek jadwal sholat"
"inget ini: gua biasanya trading jam 9 malem"
"screenshot https://example.com"
"like https://x.com/some/tweet"
```

Upload PDF/Word/Excel → bot baca & analisis.
Voice note → bot transcribe (Whisper) & proses.

---

## 🗺️ Roadmap

### ✅ Phase 0 — Security & refactor (current PR)
- [x] OWNER_TELEGRAM_IDS allow-list (multi-owner support)
- [x] Dangerous-command approval flow via Telegram buttons
- [x] Replace `/root/aiagent/` hardcoded paths dengan `BASE_DIR`
- [x] `pyproject.toml` + `requirements.txt` (pinned)
- [x] `.env.example`, `AGENTS.md`, `SOUL.md` Hermes-style
- [x] Proper logging (`logging_setup.py`)
- [x] `.gitignore` hardening + remove `.env`/`*.db`/`*.log`/cookies dari tracked files
- [x] GitHub Actions CI (ruff + pytest)
- [x] Smoke tests + auth tests

### 🔧 Phase 1 — Core Hermes parity (next)
- [ ] Gateway abstraction (Telegram + Discord + Email skeleton)
- [ ] Sessions (resumable, FTS5 search)
- [ ] Profiles (switch persona on the fly)
- [ ] Natural-language cron (replace hardcoded scheduler)
- [ ] Structured action dispatcher (replace string parsing)
- [ ] Skill curator + auto-improve
- [ ] Provider abstraction (Groq / OpenAI / Anthropic / Ollama)
- [ ] Browser tool refactor (drop inline subprocess script string)
- [ ] EDIT_FILE re-enabled dengan approval flow

### ⚡ Phase 2 — Power features
- [ ] Delegation / subagents (parallel isolated work)
- [ ] Persistent goals (Ralph loop)
- [ ] MCP client
- [ ] Image generation tool
- [ ] TTS output
- [ ] Plugin system + hooks
- [ ] API server (OpenAI-compatible)

### 🚀 Phase 3 — Niche (optional)
- [ ] Docker sandbox untuk EXECUTE_BASH
- [ ] Git worktree multi-agent
- [ ] Kanban task board
- [ ] Batch processing
- [ ] Local Ollama provider

---

## 🔑 API Keys

| Service | Daftar | Harga |
|---|---|---|
| Telegram Bot | `@BotFather` di Telegram | Free |
| Groq AI | console.groq.com | Free |
| Tavily Search | tavily.com | Free (1000/bln) |
| Google Calendar | console.cloud.google.com | Free |
| Gmail App Password | myaccount.google.com/apppasswords | Free |
| Binance Futures | binance.com (opsional, untuk auto-trader) | Free |
| Alpha Vantage | alphavantage.co (opsional) | Free |

---

## 👤 Author

Dibuat oleh jagresman (eki) — Bandung, Indonesia.
Terinspirasi dari [Hermes Agent](https://hermes-agent.nousresearch.com/) by Nous Research.
