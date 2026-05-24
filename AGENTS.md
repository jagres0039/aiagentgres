# AGENTS.md — Project Context

Dokumen ini di-load otomatis oleh `aiagentgres` setiap percakapan (mirip `AGENTS.md` /
`CLAUDE.md` di Hermes Agent / Claude Code). Isi sini konteks high-level tentang project lo:

- Tujuan project
- Arsitektur global
- Konvensi koding
- Hal yang HARUS dilakukan / HARUS dihindari
- Daftar tools / skills tambahan

Beda dari `SOUL.md` (personality / cara ngomong) dan `knowledge.txt` (fakta pribadi user).

---

## Project Goal

`aiagentgres` adalah Personal AI Agent berbasis Telegram + Groq, terinspirasi
[Hermes Agent](https://hermes-agent.nousresearch.com/) by Nous Research.
Target jangka panjang: self-improving multi-platform agent dengan persistent
memory, skill auto-creation, dan safe code execution.

## Coding Conventions

- Python 3.10+, type-hinted module baru.
- Logging via `logging_setup.get_logger(__name__)`, bukan `print()`.
- Path dari `paths.BASE_DIR`, jangan hardcode `/root/aiagent/`.
- Setiap handler Telegram yang sensitive WAJIB di-guard `auth.is_authorized(user_id)`.
- Action LLM yang destructive (`EXECUTE_BASH`, `EDIT_FILE`, dll) WAJIB lewat
  approval flow kalau `auth.requires_approval(cmd)` mengembalikan True.

## Do / Don't

- DO: tambah skill di `skills/<nama>/SKILL.md` dengan YAML frontmatter.
- DO: pakai env var (lewat `config.py`) untuk credential, jangan hardcode.
- DON'T: commit `.env`, `*.db`, `*.log`, cookie jar, atau service-account key.
- DON'T: ubah `agent_backup.py` (legacy, akan dihapus di Phase 1 refactor).
