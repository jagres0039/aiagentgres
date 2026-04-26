from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL
from memory import (add_message, get_history, save_memory,
                    get_memory_prompt, get_all_memories_text, delete_memory)
from tools.calendar_tool import create_event
from tools.search_tool import web_search as do_web_search, search_news
from tools.gmail_tool import send_email, read_inbox, read_email_content
from skill_loader import get_skills_prompt, get_skill_names
from skill_executor import execute_skill
from skill_writer import write_skill, list_skills, delete_skill, improve_skill
from datetime import datetime
from skill_loader import get_skills_prompt, get_skill_names, match_skill
import os
import re

SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')

# API Keys rotation
try:
    from config import GROQ_API_KEY_2
except:
    GROQ_API_KEY_2 = None
try:
    from config import GROQ_API_KEY_3
except:
    GROQ_API_KEY_3 = None
try:
    from config import GROQ_API_KEY_4
except:
    GROQ_API_KEY_4 = None

API_KEYS = [k for k in [GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3, GROQ_API_KEY_4] if k]
current_key_index = 0

def get_client():
    return Groq(api_key=API_KEYS[current_key_index])

def rotate_key():
    global current_key_index
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    print(f"🔄 Rotating ke API key #{current_key_index + 1}")
    return Groq(api_key=API_KEYS[current_key_index])

def load_knowledge() -> str:
    knowledge_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'knowledge.txt'
    )
    if os.path.exists(knowledge_file):
        with open(knowledge_file, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def detect_action(text):
    lines = text.strip().split('\n')
    for line in lines:
        clean_line = line.strip()
        line_upper = clean_line.upper()
        
        if line_upper.startswith("SEARCH:"):
            return "SEARCH", clean_line[7:].strip()
        elif line_upper.startswith("NEWS:"):
            return "NEWS", clean_line[5:].strip()
        elif line_upper.startswith("CALENDAR:"):
            return "CALENDAR", clean_line[9:].strip()
        elif line_upper.startswith("EMAIL:"):
            return "EMAIL", clean_line[6:].strip()
        elif line_upper.startswith("INBOX:"):
            return "INBOX", clean_line[6:].strip()
        elif line_upper.startswith("READ_EMAIL:"):
            return "READ_EMAIL", clean_line[11:].strip()
        elif line_upper.startswith("REMEMBER:"):
            return "REMEMBER", clean_line[9:].strip()
        elif line_upper.startswith("SHOW_MEMORY:"):
            return "SHOW_MEMORY", ""
        elif line_upper.startswith("FORGET:"):
            return "FORGET", clean_line[7:].strip()
        elif line_upper.startswith("CREATE_SKILL:"):
            return "CREATE_SKILL", clean_line[13:].strip()
        elif line_upper.startswith("LIST_SKILLS:"):
            return "LIST_SKILLS", ""
        elif line_upper.startswith("DELETE_SKILL:"):
            return "DELETE_SKILL", clean_line[13:].strip()
        elif line_upper.startswith("IMPROVE_SKILL:"):
            return "IMPROVE_SKILL", clean_line[14:].strip()
        elif line_upper.startswith("CREATE_EXCEL:"):
            return "CREATE_EXCEL", clean_line[13:].strip()
        elif line_upper.startswith("CREATE_WORD:"):
            return "CREATE_WORD", clean_line[12:].strip()
            
        elif "EXECUTE_BASH:" in line_upper:
            idx = line_upper.find("EXECUTE_BASH:")
            return "EXECUTE_BASH", clean_line[idx + 13:].strip()
            
        elif "EDIT_FILE:" in line_upper:
            idx = line_upper.find("EDIT_FILE:")
            return "EDIT_FILE", clean_line[idx + 10:].strip()
            
        elif line_upper.startswith("SKILL:"):
            return "SKILL", clean_line[6:].strip()
        elif line_upper.startswith("L:"):
            return "SKILL", clean_line[2:].strip()
        elif line_upper.startswith("S:"):
            return "SKILL", clean_line[2:].strip()

    return None, None

async def execute_matched_skill(skill_name: str, user_message: str, user_id: int) -> str:
    """Eksekusi skill yang sudah dideteksi"""
    try:
        skill_md_path = os.path.join(SKILLS_DIR, skill_name, 'SKILL.md')
        if not os.path.exists(skill_md_path):
            return f"❌ Skill '{skill_name}' tidak ditemukan."

        with open(skill_md_path, 'r') as f:
            skill_content = f.read()

        # Extract kode Python
        code_start = skill_content.find("CODE:\n") + 6
        if code_start < 6:
            code_start = skill_content.find("CODE:") + 5

        code = skill_content[code_start:].strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()

        # Extract stock code
        stock_codes = re.findall(r'\b[A-Z]{3,5}\b', user_message.upper())
        excluded = {
            'XAU', 'USD', 'EUR', 'GBP', 'JPY', 'IDR', 'BTC', 'ETH', 'SOL',
            'BNB', 'XRP', 'ADA', 'DOT', 'SAHAM', 'FOREX', 'GOLD', 'CRYPTO',
            'MARKET', 'IHSG', 'HARI', 'INI', 'ANALISA', 'ANALISIS',
            'SCREENING', 'SKILL', 'BUAT', 'CEK', 'LIHAT', 'TOLONG'
        }
        stock_code = next((s for s in stock_codes if s not in excluded), "BBCA")

        # Replace variabel dinamis
        code = code.replace('kode = "BBCA"', f'kode = "{stock_code}"')
        code = code.replace("kode = 'BBCA'", f"kode = '{stock_code}'")

        return execute_skill(skill_name, code)

    except Exception as e:
        return f"❌ Error eksekusi skill: {str(e)}"

async def run_agent(user_id: int, user_message: str, context=None) -> str:
    current_now = datetime.now().strftime("%Y-%m-%d %H:%M")
    current_today = datetime.now().strftime("%Y-%m-%d")
    skills_prompt = get_skills_prompt()
    manual_knowledge = load_knowledge()
    memory_prompt = get_memory_prompt(user_id)

# Smart skill matching — cek dulu sebelum tanya AI
    matched_skill = match_skill(user_message)
    if matched_skill:
        print(f"DEBUG smart match: {matched_skill}")
        # Langsung eksekusi skill tanpa tanya AI
        action = "SKILL"
        value = matched_skill
        # Skip AI call, langsung ke handler SKILL
        add_message(user_id, "user", user_message)
        reply = await execute_matched_skill(matched_skill, user_message, user_id)
        add_message(user_id, "assistant", reply)
        return reply

    system = f"""Kamu adalah personal AI assistant tingkat lanjut. Hari ini {current_now} WIB.

IDENTITAS:
{manual_knowledge}

MEMORY:
{memory_prompt if memory_prompt else "Kosong."}

EXECUTE_BASH: <perintah_terminal_linux>
EDIT_FILE: <path_file_absolut> | <kode_baru_lengkap>

SKILLS TERSEDIA:
{skills_prompt}

RULE UTAMA — WAJIB DIIKUTI 100%:
Kalau user minta aksi, balas HANYA dengan 1 baris format di bawah, tanpa teks lain.

FORMAT YANG TERSEDIA:
SEARCH: <query>
NEWS: <query>
CALENDAR: <title>|<YYYY-MM-DDThh:mm:ss>|<YYYY-MM-DDThh:mm:ss>|<desc>
EMAIL: <to>|<subject>|<body>
INBOX: <jumlah>
READ_EMAIL: <nomor>
REMEMBER: <key>|<value>
SHOW_MEMORY:
FORGET: <key>
CREATE_SKILL: <nama>|<deskripsi>
LIST_SKILLS:
DELETE_SKILL: <nama>
IMPROVE_SKILL: <nama>|<improvement>
CREATE_EXCEL: <topik_bebas>
CREATE_WORD: <judul>|<konten>
SKILL: <nama_skill>

ATURAN KETAT MEMILIH FORMAT (DILARANG SALAH TANGKAP):
1. HARAM MENGGUNAKAN SKILL JIKA USER MINTA EXCEL/TABEL!
   Jika user mengetik "buatin excel", "bikin excel", "tabel", "spreadsheet": WAJIB gunakan CREATE_EXCEL: <topik>. 
   Walaupun ada kata "forex", "crypto", "saham", TETAP GUNAKAN CREATE_EXCEL.
2. JIKA user minta analisa, screening, atau cek market: BARU gunakan SKILL: <nama_skill>.

ATURAN GOD MODE (VPS & KODE):
1. Jika user minta info sistem, cek RAM, install library (pip), restart bot, atau urusan Linux lainnya → WAJIB gunakan EXECUTE_BASH: <perintah>.
2. Jika user minta mengubah, memperbaiki, atau menulis ulang kodingan di file tertentu → WAJIB gunakan EDIT_FILE: /root/aiagent/<namafile> | <isi_kode_lengkap_tanpa_terpotong>.
3. SELF-HEALING: Jika user mengirimkan log ERROR Python atau Bash, analisa errornya, lalu gunakan EDIT_FILE atau EXECUTE_BASH untuk memperbaikinya secara otonom!

CONTOH BENAR BIAR TIDAK SALAH TANGKAP:
User: "buatin excel buat trading forex" → CREATE_EXCEL: trading forex
User: "bikin excel jurnal matematika" → CREATE_EXCEL: jurnal matematika kelas
User: "analisa forex dong" → SKILL: screening_forex
User: "buat event besok jam 10" → CALENDAR: Meeting|{current_today}T10:00:00|{current_today}T11:00:00|
User: "cari berita crypto" → NEWS: crypto news today

Pertanyaan biasa → jawab normal santai pakai bahasa gaul, gunakan kata "lo/gua"."""


    add_message(user_id, "user", user_message)
    messages = [{"role": "system", "content": system}] + get_history(user_id)

    last_error = None
    response = None

    for i in range(len(API_KEYS)):
        try:
            client = get_client()
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=1024,
            )
            break
        except Exception as e:
            if '429' in str(e) or 'rate_limit' in str(e).lower():
                print(f"⚠️ Key #{current_key_index + 1} kena rate limit, rotate...")
                rotate_key()
                last_error = e
            else:
                return f"❌ Error dari AI: {str(e)}"

    if response is None:
        return f"❌ Semua API key kena rate limit. Tunggu beberapa menit ya bro!"

    reply = response.choices[0].message.content.strip()
    action, value = detect_action(reply)

    print(f"DEBUG raw: {repr(reply[:150])}")
    print(f"DEBUG action={action} value={value[:80] if value else ''}")

    # Handler SEARCH
    if action == "SEARCH":
        search_result = do_web_search(value)
        try:
            client = get_client()
            summary = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": """Rangkum hasil search dengan format rapi.
WAJIB:
- Gunakan HANYA angka/data yang ada di hasil search
- Bahasa Indonesia santai, pakai 'lo' bukan 'kamu'
- Gunakan emoji yang relevan
- Format poin-poin pendek dan jelas
- Sebutin sumber di akhir
DILARANG:
- Jangan ubah angka dari hasil search
- Jangan karang data sendiri"""},
                    {"role": "user", "content": f"Pertanyaan: {user_message}\n\nHasil:\n{search_result}"}
                ],
                max_tokens=512,
            )
            reply = summary.choices[0].message.content
        except Exception:
            reply = search_result

    # Handler NEWS
    elif action == "NEWS":
        news_result = search_news(value)
        try:
            client = get_client()
            summary = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": """Rangkum berita dengan format rapi.
- Bahasa Indonesia santai, pakai 'lo' bukan 'kamu'
- Gunakan emoji yang relevan
- Format per berita dengan jelas
- Sebutin sumber di akhir"""},
                    {"role": "user", "content": f"Topik: {user_message}\n\nBerita:\n{news_result}"}
                ],
                max_tokens=512,
            )
            reply = summary.choices[0].message.content
        except Exception:
            reply = news_result

    # Handler CALENDAR
    elif action == "CALENDAR":
        try:
            parts = value.split("|")
            reply = create_event(
                title=parts[0].strip(),
                start_time=parts[1].strip(),
                end_time=parts[2].strip(),
                description=parts[3].strip() if len(parts) > 3 else ""
            )
        except Exception as e:
            reply = f"❌ Error buat event: {str(e)}"

    # Handler EMAIL
    elif action == "EMAIL":
        try:
            parts = value.split("|")
            reply = send_email(
                to=parts[0].strip(),
                subject=parts[1].strip(),
                body=parts[2].strip()
            )
        except Exception as e:
            reply = f"❌ Error kirim email: {str(e)}"

    # Handler INBOX
    elif action == "INBOX":
        try:
            max_results = int(value) if value.isdigit() else 5
            reply = read_inbox(max_results)
        except Exception as e:
            reply = f"❌ Error baca inbox: {str(e)}"

    # Handler READ_EMAIL
    elif action == "READ_EMAIL":
        try:
            index = int(value) if value.isdigit() else 1
            reply = read_email_content(index)
        except Exception as e:
            reply = f"❌ Error baca email: {str(e)}"

    # Handler REMEMBER
    elif action == "REMEMBER":
        try:
            parts = value.split("|")
            key = parts[0].strip()
            val = parts[1].strip()
            save_memory(user_id, key, val)
            reply = f"✅ Oke gua inget — {key}: {val}"
        except Exception as e:
            reply = f"❌ Gagal simpan memory: {str(e)}"

    # Handler SHOW_MEMORY
    elif action == "SHOW_MEMORY":
        reply = get_all_memories_text(user_id)

    # Handler FORGET
    elif action == "FORGET":
        try:
            delete_memory(user_id, value)
            reply = f"🗑️ Oke gua udah lupa soal '{value}'"
        except Exception as e:
            reply = f"❌ Gagal hapus memory: {str(e)}"

    # Handler CREATE_SKILL
    elif action == "CREATE_SKILL":
        try:
            parts = value.split("|")
            skill_name = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else skill_name
            if context:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏳ Lagi nulis skill '{skill_name}'... tunggu sebentar!"
                )
            reply = write_skill(skill_name, description)
        except Exception as e:
            reply = f"❌ Error buat skill: {str(e)}"

    # Handler LIST_SKILLS
    elif action == "LIST_SKILLS":
        reply = list_skills()

    # Handler DELETE_SKILL
    elif action == "DELETE_SKILL":
        try:
            reply = delete_skill(value)
        except Exception as e:
            reply = f"❌ Error hapus skill: {str(e)}"

    # Handler IMPROVE_SKILL
    elif action == "IMPROVE_SKILL":
        try:
            parts = value.split("|")
            skill_name = parts[0].strip()
            improvement = parts[1].strip() if len(parts) > 1 else ""
            if context:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏳ Lagi improve skill '{skill_name}'... tunggu sebentar!"
                )
            reply = improve_skill(skill_name, improvement)
        except Exception as e:
            reply = f"❌ Error improve skill: {str(e)}"

    # Handler CREATE_EXCEL
    elif action == "CREATE_EXCEL":
        try:
            excel_type = value.strip().lower()
            if context:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⏳ Lagi bikin file Excel... tunggu sebentar!"
                )
            from tools.file_creator import (create_trading_journal_excel,
                                             create_airdrop_tracker_excel,
                                             create_portfolio_excel)
            if excel_type == "trading_journal":
                filepath = create_trading_journal_excel()
            elif excel_type == "airdrop_tracker":
                filepath = create_airdrop_tracker_excel()
            elif excel_type == "portfolio":
                filepath = create_portfolio_excel()
            else:
                reply = f"❌ Tipe tidak dikenal: {excel_type}"
                add_message(user_id, "assistant", reply)
                return reply

            if isinstance(filepath, str) and filepath.startswith("❌"):
                reply = filepath
            else:
                if context:
                    with open(filepath, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=user_id,
                            document=f,
                            filename=os.path.basename(filepath),
                            caption="✅ File Excel udah jadi bro!"
                        )
                reply = "✅ File Excel udah dikirim bro!"
        except Exception as e:
            reply = f"❌ Error buat Excel: {str(e)}"

    # Handler CREATE_WORD
    elif action == "CREATE_WORD":
        try:
            parts = value.split("|")
            title = parts[0].strip()
            content_text = parts[1].strip() if len(parts) > 1 else ""
            if context:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⏳ Lagi bikin file Word... tunggu sebentar!"
                )
            from tools.file_creator import create_word
            content = {
                "title": title,
                "sections": [{"heading": "Konten", "paragraphs": [content_text]}]
            }
            filename = f"dokumen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            filepath = create_word(filename, content)

            if isinstance(filepath, str) and filepath.startswith("❌"):
                reply = filepath
            else:
                if context:
                    with open(filepath, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=user_id,
                            document=f,
                            filename=os.path.basename(filepath),
                            caption="✅ File Word udah jadi bro!"
                        )
                reply = "✅ File Word udah dikirim bro!"
        except Exception as e:
            reply = f"❌ Error buat Word: {str(e)}"

    # Handler EXECUTE_BASH
    elif action == "EXECUTE_BASH":
        cmd = value.strip()
        if context:
            await context.bot.send_message(chat_id=user_id, text=f"🚀 Eksekusi Terminal: `{cmd}`...")
        
        import subprocess
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            output = res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
            if not output:
                output = "✅ Eksekusi sukses (tidak ada output teks)."
            
            # TRIK ANTI ERROR PASTE: Pake chr(96) yang artinya backtick (`)
            bt = chr(96) * 3
            reply = f"💻 Hasil `{cmd}`:\n{bt}bash\n{output[:3500]}\n{bt}"
        except Exception as e:
            reply = f"❌ Gagal eksekusi Bash: {str(e)}"

    # Handler SKILL — Dynamic, tanpa hardcode
    elif action == "SKILL":
        try:
            skill_name = value.strip()
            skill_name = skill_name.split('(')[0].strip()
            skill_name = skill_name.lower().replace(' ', '_')
            skill_name = re.sub(r'[^a-z0-9_]', '', skill_name)

            # Auto-match ke skill yang ada
            available_skills = get_skill_names()

            if skill_name not in available_skills:
                matched = next(
                    (s for s in available_skills if s in skill_name or skill_name in s),
                    None
                )
                if matched:
                    skill_name = matched
                else:
                    reply = f"❌ Skill '{skill_name}' tidak ditemukan.\n📦 Skill tersedia: {', '.join(available_skills)}"
                    add_message(user_id, "assistant", reply)
                    return reply

            # Extract stock code kalau ada
            stock_codes = re.findall(r'\b[A-Z]{3,5}\b', user_message.upper())
            excluded = {
                'XAU', 'USD', 'EUR', 'GBP', 'JPY', 'IDR', 'BTC', 'ETH', 'SOL',
                'BNB', 'XRP', 'ADA', 'DOT', 'SAHAM', 'FOREX', 'GOLD', 'CRYPTO',
                'MARKET', 'IHSG', 'HARI', 'INI', 'ANALISA', 'ANALISIS',
                'SCREENING', 'SKILL', 'BUAT', 'CEK', 'LIHAT', 'TOLONG'
            }
            stock_code = next((s for s in stock_codes if s not in excluded), "BBCA")

            # Baca kode dari SKILL.md
            skill_md_path = os.path.join(SKILLS_DIR, skill_name, 'SKILL.md')
            if not os.path.exists(skill_md_path):
                reply = f"❌ File SKILL.md tidak ditemukan untuk '{skill_name}'"
                add_message(user_id, "assistant", reply)
                return reply

            with open(skill_md_path, 'r') as f:
                skill_content = f.read()

            # Extract kode Python
            code_start = skill_content.find("CODE:\n") + 6
            if code_start < 6:
                code_start = skill_content.find("CODE:") + 5

            code = skill_content[code_start:].strip()
            if code.startswith("```python"):
                code = code[9:]
            if code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            code = code.strip()

            # Replace variabel dinamis
            code = code.replace('kode = "BBCA"', f'kode = "{stock_code}"')
            code = code.replace("kode = 'BBCA'", f"kode = '{stock_code}'")

            reply = execute_skill(skill_name, code)

        except Exception as e:
            reply = f"❌ Error eksekusi skill: {str(e)}"

    add_message(user_id, "assistant", reply)
    return reply
