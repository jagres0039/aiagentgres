# 🤖 Personal AI Agent

Personal AI Agent berbasis Telegram Bot yang ditenagai Groq AI (Llama 3.3 70B).
Dibangun dengan Python, terinspirasi dari OpenClaw AI Agent.

---

## 📁 Struktur Project
```
/root/aiagent/
├── main.py              # Entry point Telegram bot
├── agent.py             # Logika utama + handler semua perintah
├── config.py            # Konfigurasi API keys
├── memory.py            # Memory persistent (SQLite)
├── skill_loader.py      # Load semua skill otomatis
├── skill_executor.py    # Eksekusi kode dari skill
├── skill_writer.py      # Self-improving — nulis skill sendiri
├── knowledge.txt        # Pengetahuan manual tentang pemilik
├── memory.db            # Database SQLite (auto-generated)
├── .env                 # Secret keys (jangan di-commit!)
├── credentials.json     # Google Calendar credentials
├── service_account.json # Google Calendar service account
├── token_gmail.json     # Gmail token (auto-generated)
├── requirements.txt     # Dependencies
├── tools/
│   ├── calendar_tool.py # Google Calendar integration
│   ├── gmail_tool.py    # Gmail SMTP integration
│   └── search_tool.py   # Tavily web search
└── skills/
    ├── crypto/          # Cek harga crypto
    ├── portfolio/       # Portfolio tracker
    ├── weather/         # Cek cuaca
    ├── news/            # Berita terbaru
    ├── kurs/            # Kurs mata uang
    ├── notes/           # Catatan
    ├── translator/      # Translator
    ├── summarizer/      # URL summarizer
    └── [skill baru]/    # Ditambah otomatis
```

---

## ⚙️ Setup & Installation

### 1. Clone & masuk folder
```bash
cd /root/aiagent
```

### 2. Install dependencies
```bash
pip3 install python-telegram-bot groq python-dotenv \
    google-auth google-auth-oauthlib google-api-python-client \
    tavily-python ddgs pymupdf python-docx openpyxl aiosqlite
```

### 3. Setup `.env`
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
GMAIL_ADDRESS=your_gmail@gmail.com
GMAIL_APP_PASSWORD=your_16digit_app_password
```

### 4. Setup `knowledge.txt`
```
=== TENTANG PEMILIK AGENT ===
Nama: [nama lo]
Kota: Bandung, Indonesia
Timezone: WIB (UTC+7)
```

### 5. Jalanin bot
```bash
python3.11 main.py
```

---

## 🚀 Fitur

### Core
| Fitur | Status | Keterangan |
|---|---|---|
| Telegram Bot | ✅ | Interface utama |
| Groq AI (Llama 3.3 70B) | ✅ | Otak agent |
| Memory Persistent | ✅ | SQLite, ingat walau restart |
| Voice Note | ✅ | Whisper transcription |
| Baca File | ✅ | PDF, Word, Excel |
| Knowledge Base | ✅ | knowledge.txt |

### Tools
| Tool | Status | Keterangan |
|---|---|---|
| Web Search | ✅ | Tavily API |
| News Search | ✅ | Tavily news |
| Google Calendar | ✅ | Service Account |
| Gmail | ✅ | SMTP App Password |

### Skills System (OpenClaw style)
| Skill | Status | Keterangan |
|---|---|---|
| Crypto Price | ✅ | CoinGecko API |
| Portfolio Tracker | ✅ | Multi-coin |
| Weather | ✅ | wttr.in |
| News Crypto | ✅ | CryptoPanic |
| Kurs Mata Uang | ✅ | Realtime |
| Translator | ✅ | Google Translate |
| URL Summarizer | ✅ | Extract & summarize |
| Note Taking | ✅ | Simpan catatan |
| Self-improving | ✅ | Nulis skill sendiri |

---

## 💬 Cara Pakai

### Commands Telegram
```
/start   - Mulai bot
/clear   - Hapus history chat
/memory  - Lihat semua memory tersimpan
```

### Contoh Perintah
```
# Web Search
"cariin info terbaru soal Bitcoin"
"berita crypto hari ini"

# Calendar
"buat event meeting besok jam 10 pagi sampai jam 11"
"ingetin gua besok jam 3 sore"

# Email
"cek inbox gua"
"kirimin email ke xxx@gmail.com subject Test isi: Halo!"
"baca email pertama"

# Crypto
"berapa harga BTC sekarang?"
"cek portfolio gua"
"fear and greed index sekarang?"

# Skill Management
"buatin skill buat cek jadwal sholat"
"lihat semua skill yang ada"
"improve skill crypto biar tampilin market cap juga"
"hapus skill xxx"

# Memory
"inget ini: gua biasanya trading jam 9 malem"
/memory
"lupain soal xxx"

# File
# Upload PDF/Word/Excel → bot langsung baca & analisis
# Upload dengan caption "analisis data ini" → bot analisis sesuai perintah

# Voice Note
# Kirim VN → bot transcribe & proses otomatis
```

---

## 🧠 Skills System

Skills disimpan di folder `skills/` — setiap skill punya `SKILL.md` berisi instruksi untuk AI.

### Tambah Skill Manual
```bash
mkdir -p /root/aiagent/skills/nama_skill
nano /root/aiagent/skills/nama_skill/SKILL.md
```

### Tambah Skill via Telegram
```
"buatin skill buat [deskripsi]"
```

### Format SKILL.md
```markdown
## Skill: Nama Skill

### Deskripsi
Apa yang skill ini lakukan.

### Trigger
Kapan skill ini dipanggil.

### Cara Pakai
SKILL: nama_skill
CODE:
import requests
# kode python di sini
print("output")
```

---

## 🗺️ Roadmap

### ✅ Done
- Telegram Bot + Groq AI
- Google Calendar
- Web Search (Tavily)
- News Search
- Skills System (OpenClaw style)
- Voice Note (Whisper)
- Baca PDF, Word, Excel
- Knowledge base personal
- Gmail (kirim & baca)
- Memory Persistent (SQLite)
- Self-improving Agent

### ⏳ Next
- [ ] Morning Briefing otomatis
- [ ] Price Alert crypto
- [ ] Scheduler/Cron otomatis
- [ ] Browser automation (Playwright)
- [ ] Airdrop automation
- [ ] Wallet balance checker
- [ ] Trading agent
- [ ] Google Sheets integration
- [ ] Multi-agent system

---

## 🔧 Troubleshooting

### Bot tidak response
```bash
python3.11 main.py
# Cek error di terminal
```

### Restart bot
```bash
# Ctrl+C untuk stop
python3.11 main.py
```

### Cek semua file
```bash
ls -la /root/aiagent/
ls -la /root/aiagent/skills/
ls -la /root/aiagent/tools/
```

### Backup project
```bash
tar -czf aiagent_backup_$(date +%Y%m%d).tar.gz /root/aiagent/
```

### Reset memory
```bash
rm /root/aiagent/memory.db
python3.11 main.py
```

---

## 📦 Dependencies
```
python-telegram-bot==20.6
groq==1.1.1
python-dotenv==1.2.1
tavily-python
ddgs
google-auth
google-auth-oauthlib
google-api-python-client
pymupdf
python-docx
openpyxl
aiosqlite
requests
```

---

## 🔑 API Keys yang Dibutuhkan

| Service | Link Daftar | Harga |
|---|---|---|
| Telegram Bot | @BotFather di Telegram | Gratis |
| Groq AI | console.groq.com | Gratis |
| Tavily Search | tavily.com | Gratis (1000/bln) |
| Google Calendar | console.cloud.google.com | Gratis |
| Gmail App Password | myaccount.google.com/apppasswords | Gratis |

---

## 👤 Author

Dibuat dengan ❤️ jagresman(eki)
Kota: Bandung, Indonesia
Terinspirasi dari: OpenClaw AI Agent
