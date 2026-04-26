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
import glob
import time # Nambah time buat jeda retry

SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')
OUTPUT_DIR = "/root/aiagent/output_office"

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
            
        elif "SCREENSHOT:" in line_upper:
            idx = line_upper.find("SCREENSHOT:")
            return "SCREENSHOT", clean_line[idx + 11:].strip()
            
        elif "SCREENSHOT_FULL:" in line_upper:
            idx = line_upper.find("SCREENSHOT_FULL:")
            return "SCREENSHOT_FULL", clean_line[idx + 16:].strip()

        elif "AUTO_RETWEET:" in line_upper:
            idx = line_upper.find("AUTO_RETWEET:")
            return "AUTO_RETWEET", clean_line[idx + 13:].strip()

        elif "AUTO_LIKE:" in line_upper:
            idx = line_upper.find("AUTO_LIKE:")
            return "AUTO_LIKE", clean_line[idx + 10:].strip()

        elif "AUTO_POST:" in line_upper:
            idx = line_upper.find("AUTO_POST:")
            return "AUTO_POST", clean_line[idx + 10:].strip()
        elif "AUTO_REPLY:" in line_upper:
            idx = line_upper.find("AUTO_REPLY:")
            return "AUTO_REPLY", clean_line[idx + 11:].strip()
        elif "AUTO_LRT:" in line_upper:
            idx = line_upper.find("AUTO_LRT:")
            return "AUTO_LRT", clean_line[idx + 9:].strip()
        elif "AUTO_FOLLOW:" in line_upper:
            idx = line_upper.find("AUTO_FOLLOW:")
            return "AUTO_FOLLOW", clean_line[idx + 12:].strip()
        elif line_upper.startswith("SKILL:"):
            return "SKILL", clean_line[6:].strip()
        elif line_upper.startswith("L:"):
            return "SKILL", clean_line[2:].strip()
        elif line_upper.startswith("S:"):
            return "SKILL", clean_line[2:].strip()
        elif "CREATE_FILE:" in line_upper:
            idx = line_upper.find("CREATE_FILE:")
            return "CREATE_FILE", clean_line[idx + 12:].strip()
        elif "SUPER_FIX:" in line_upper:
            idx = line_upper.find("SUPER_FIX:")
            return "SUPER_FIX", clean_line[idx + 10:].strip()
        elif "DEBUG_CHAT:" in line_upper:
            idx = line_upper.find("DEBUG_CHAT:")
            return "DEBUG_CHAT", clean_line[idx + 11:].strip()

    return None, None

async def handle_file_delivery(user_id, context):
    """Mencari file terbaru di output_office dan mengirimkannya via Telegram"""
    if not context: return
    try:
        if not os.path.exists(OUTPUT_DIR): return
        files = glob.glob(os.path.join(OUTPUT_DIR, "*"))
        if not files: return
        
        latest_file = max(files, key=os.path.getctime)
        if (datetime.now() - datetime.fromtimestamp(os.path.getctime(latest_file))).seconds < 45:
            with open(latest_file, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=os.path.basename(latest_file),
                    caption="✅ File dokumen lu udah jadi bro!"
                )
    except Exception as e:
        print(f"❌ Error Delivery: {str(e)}")

async def execute_matched_skill(skill_name: str, user_message: str, user_id: int, context=None) -> str:
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
        
        # 🔥 FITUR BARU: Pastikan kode tidak kosong sebelum dieksekusi
        if not code:
            return f"❌ Skill '{skill_name}' gak punya kode yang bisa dijalain bro."
            
        code = f"PESAN_USER = {repr(user_message)}\n" + code

        # Extract stock code
        stock_codes = re.findall(r'\b[A-Z]{2,7}\b', user_message.upper())
        kata_sampah = {
            'TOLONG', 'ANALISA', 'ANALISIS', 'SEKARANG', 'PAKAI', 'MENGGUNAKAN', 
            'SKILL', 'KOIN', 'SAHAM', 'CRYPTO', 'WAKTU', 'SAAT', 'WIB', 'INI', 
            'SISTEM', 'TANGGAL', 'JAM', 'DONG', 'COBA', 'KASIH', 'LIHAT', 'CEK',
            'HARI', 'MARKET', 'GOLD', 'FOREX', 'BUAT', 'YANG', 'DARI', 'PADA'
        }
        stock_code = next((s for s in stock_codes if s not in kata_sampah), "BBCA")

        # Replace variabel dinamis
        code = code.replace('kode = "BBCA"', f'kode = "{stock_code}"')
        code = code.replace("kode = 'BBCA'", f"kode = '{stock_code}'")

        reply = execute_skill(skill_name, code)
        
        if skill_name == "universal_office_engine":
            await handle_file_delivery(user_id, context)
            
        return reply

    except Exception as e:
        # 🔥 FITUR BARU: Tangkap error 'choices' dari Vision API skill
        if "'choices'" in str(e):
            return f"❌ Skill '{skill_name}' gagal bro. Kayaknya Groq Vision API ngasih respon kosong atau error struktural. Coba cek log skillnya!"
        return f"❌ Error eksekusi skill '{skill_name}': {str(e)}"

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
        reply = await execute_matched_skill(matched_skill, user_message, user_id, context)
        add_message(user_id, "assistant", reply)
        return reply

    system = f"""Kamu adalah personal AI assistant tingkat lanjut bernama JAGRESMAN. Hari ini {current_now} WIB.

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
SKILL: <nama_skill>
SCREENSHOT: <url_website_dengan_https>
AUTO_LIKE: <url_tweet> (Gunakan ini jika user menyuruh like / menyukai postingan Twitter/X)
AUTO_POST: <isi_tweet> (Gunakan ini jika user menyuruh membuat postingan/tweet baru)
AUTO_REPLY: <url_tweet> | <isi_komentar> (Gunakan ini jika user menyuruh membalas/mengomentari tweet orang lain. WAJIB gunakan pemisah |)
AUTO_LRT: <url_tweet> (Gunakan ini jika user menyuruh untuk Like dan Retweet/Repost sekaligus pada satu postingan)
AUTO_FOLLOW: <url_profil> (Gunakan ini jika user menyuruh untuk Follow akun Twitter/X orang lain)
Gunakan CREATE_FILE untuk membuat file baru, SUPER_FIX untuk memperbaiki file di VPS yang error, dan DEBUG_CHAT untuk membantu user debugging kode dari VS Code via chat.

ATURAN KETAT MEMILIH FORMAT (DILARANG SALAH TANGKAP):
1. HARAM MENGGUNAKAN SKILL JIKA USER MINTA EXCEL/TABEL!
   Jika user mengetik "buatin excel", "bikin excel", "tabel", "spreadsheet", "rapihin data": WAJIB gunakan SKILL: universal_office_engine. 
   Walaupun ada kata "forex", "crypto", "saham", TETAP GUNAKAN SKILL: universal_office_engine.
2. JIKA user minta analisa, screening, atau cek market: BARU gunakan SKILL: <nama_skill>.

ATURAN GOD MODE (VPS & KODE):
1. Jika user minta info sistem, cek RAM, install library (pip), restart bot, atau urusan Linux lainnya -> WAJIB gunakan EXECUTE_BASH: <perintah>.
2. Jika user minta mengubah, memperbaiki, atau menulis ulang kodingan di file tertentu -> WAJIB gunakan EDIT_FILE: /root/aiagent/<namafile> | <isi_kode_lengkap_tanpa_terpotong>.
3. SELF-HEALING: Jika user mengirimkan log ERROR Python atau Bash, analisa errornya, lalu gunakan EDIT_FILE atau EXECUTE_BASH untuk memperbaikinya secara otonom! Jika sebuah skill gagal dengan error API, coba gunakan SEARCH untuk mencari tahu mengapa API tersebut gagal atau gunakan DEBUG_CHAT untuk menganalisa kode skill tersebut.
4. Jika user minta foto, ss, atau screenshot website/chart -> WAJIB SCREENSHOT: <url>
5. Jika user menyuruh kamu untuk melakukan Retweet/Repost sebuah link Twitter, kamu DILARANG membalas dengan kalimat biasa. Kamu WAJIB merespon HANYA dengan format ini: AUTO_RETWEET: <url_tweet>

CONTOH BENAR BIAR TIDAK SALAH TANGKAP:
User: "buatin excel buat trading forex" -> SKILL: universal_office_engine
User: "bikin word makalah matematika" -> SKILL: universal_office_engine
User: "analisa forex dong" -> SKILL: screening_forex
User: "buat event besok jam 10" -> CALENDAR: Meeting|{current_today}T10:00:00|{current_today}T11:00:00|
User: "cari berita crypto" -> NEWS: crypto news today

Pertanyaan biasa -> jawab normal santai pakai bahasa gaul, gunakan kata "lo/gua"."""

    add_message(user_id, "user", user_message)

    # ===============================================================
    # 🔥 FITUR BARU 1: AUTO-SKILL BUILDER (SOP GHAIB ANTI-ERROR)
    # ===============================================================
    bt = chr(96) * 3
    kata_kunci = ["bikin skill", "bikinin skill", "buat skill", "buatkin skill"]
    if any(k in user_message.lower() for k in kata_kunci):
        system += (
            "\n\n[SISTEM RAHASIA: Bos lu memerintahkan pembuatan skill bot otomatis.\n"
            f"Lu WAJIB merespon HANYA dengan format kode blok markdown ({bt}markdown ... {bt}).\n"
            "DILARANG KERAS memberikan penjelasan, salam, atau teks basa-basi di luar blok kode tersebut!\n"
            "Di dalam blok kode, format SKILL.md WAJIB lengkap berisi meta (name, description, triggers, priority) dan CODE.]"
        )
    # ===============================================================

    messages = [{"role": "system", "content": system}] + get_history(user_id)

    last_error = None
    response = None
    reply = None # Inisialisasi reply

    # 🔥 FITUR BARU 2: Robust Retry Loop dengan Rotate Key otomatis
    total_keys = len(API_KEYS)
    for i in range(total_keys):
        try:
            client = get_client()
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=1024,
            )
            # Jika respon sukses, pastikan ada isinya
            if not response or not response.choices or not response.choices[0].message.content:
                raise Exception("Respon API kosong dari Groq.")
                
            reply = response.choices[0].message.content.strip()
            break # Berhasil, keluar loop retry
        except Exception as e:
            last_error = e
            # Jika rate limit (429), rotate key dan coba lagi
            if '429' in str(e) or 'rate_limit' in str(e).lower():
                print(f"⚠️ Key #{current_key_index + 1} kena rate limit, rotate...")
                rotate_key()
                if i < total_keys - 1: # Jangan tidur kalau masih ada key lain
                    time.sleep(1) # Jeda dikit
                continue
            else:
                # Error struktural lainnya (400, 500, etc.), jangan retry tapi laporkan
                reply = f"❌ Error struktural dari Groq API: {str(e)}"
                break # Berhenti, error bukan masalah rate limit

    if not reply and last_error:
        return f"❌ Semua API key ({total_keys}) gagal dieksekusi bro. Error terakhir: {str(last_error)}"
    elif not reply:
        return f"❌ Terjadi error aneh, reply AI kosong tanpa log error bro."

    # ===============================================================
    # 🦖 FITUR BARU 3: TANGAN ROBOT (ANTI-ERROR REGEX)
    # ===============================================================
    bt = chr(96) * 3
    if bt in reply and "name:" in reply:
        pola_ekstrak = bt + r"(?:markdown|md)?\n(.*?)\n" + bt
        match_kodingan = re.search(pola_ekstrak, reply, re.DOTALL | re.IGNORECASE)
        
        if match_kodingan:
            kodingan_bersih = match_kodingan.group(1).strip()
            match_nama = re.search(r'^name:\s*(.+)$', kodingan_bersih, re.MULTILINE)
            
            if match_nama:
                nama_folder = match_nama.group(1).strip().replace(" ", "_").lower()
                path_folder = os.path.join(SKILLS_DIR, nama_folder)
                
                try:
                    os.makedirs(path_folder, exist_ok=True)
                    path_file = os.path.join(path_folder, "SKILL.md")
                    
                    with open(path_file, "w", encoding="utf-8") as f:
                        f.write(kodingan_bersih)
                        
                    pesan_sukses = (
                        f"\n\n✅ [SYSTEM] Tangan Robot Aktif!\n"
                        f"Skill [{nama_folder}] udah sukses dicetak ke VPS bosku!\n"
                        f"📂 Folder: {path_folder}\n"
                        f"🚀 Langsung tes ketik triggernya!"
                    )
                    reply += pesan_sukses
                except Exception as e:
                    reply += f"\n\n❌ [SYSTEM ERROR] Gagal nulis file ke VPS: {str(e)}"
    # ===============================================================

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
            if summary.choices and summary.choices[0].message.content:
                reply = summary.choices[0].message.content
            else:
                reply = search_result
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
            if summary.choices and summary.choices[0].message.content:
                reply = summary.choices[0].message.content
            else:
                reply = news_result
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

    # Handler CREATE_EXCEL (Dinonaktifkan - dipaksa masuk ke universal_office_engine)
    elif action == "CREATE_EXCEL":
        reply = await execute_matched_skill("universal_office_engine", user_message, user_id, context)

    # Handler CREATE_WORD (Dinonaktifkan - dipaksa masuk ke universal_office_engine)
    elif action == "CREATE_WORD":
        reply = await execute_matched_skill("universal_office_engine", user_message, user_id, context)

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
            
            bt = chr(96) * 3
            reply = f"💻 Hasil `{cmd}`:\n{bt}bash\n{output[:3500]}\n{bt}"
        except Exception as e:
            reply = f"❌ Gagal eksekusi Bash: {str(e)}"

    # Handler SCREENSHOT (Biasa & Full)
    elif action in ["SCREENSHOT", "SCREENSHOT_FULL"]:
        url = value.strip()
        if not url.startswith("http"):
            url = "https://" + url
            
        # OTOMATIS: Ubah twitter.com jadi x.com biar kuncinya pas!
        url = url.replace("twitter.com", "x.com")
            
        is_full = "True" if action == "SCREENSHOT_FULL" else "False"
        tipe_ss = "Full Page" if action == "SCREENSHOT_FULL" else "Layar Biasa"
            
        if context:
            await context.bot.send_message(chat_id=user_id, text=f"📸 Sabar bro, AI lagi jepret {url} (Mode: {tipe_ss})...")
        
        import subprocess
        
        script = f"""
from playwright.sync_api import sync_playwright
import time
import os

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, 
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        cookie_file = '/root/aiagent/playwright_cookies.json'
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        # BIKIN SIMPEL: Kalau file cookies ada, sikat langsung pake!
        if os.path.exists(cookie_file):
            context = browser.new_context(
                viewport={{'width': 1920, 'height': 1080}}, 
                device_scale_factor=2,
                storage_state=cookie_file,
                user_agent=ua
            )
        else:
            context = browser.new_context(
                viewport={{'width': 1920, 'height': 1080}}, 
                device_scale_factor=2,
                user_agent=ua
            )
            
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}})")
        
        page.goto('{url}', timeout=60000)
        time.sleep(10)  # Nunggu 10 detik biar tweetnya ke-load semua
        
        page.screenshot(path='/root/aiagent/outputs/ss.png', full_page={is_full})
        browser.close()
except Exception as e:
    print("ERROR:", e)
"""
        try:
            os.makedirs('/root/aiagent/outputs', exist_ok=True)
            with open('/root/aiagent/tmp_ss.py', 'w') as f:
                f.write(script)
            
            res = subprocess.run("python3.11 /root/aiagent/tmp_ss.py", shell=True, capture_output=True, text=True)
            
            if os.path.exists('/root/aiagent/outputs/ss.png'):
                if context:
                    with open('/root/aiagent/outputs/ss.png', 'rb') as f:
                        await context.bot.send_photo(
                            chat_id=user_id, 
                            photo=f, 
                            caption=f"📸 Misi selesai! Ini visual dari {url}"
                        )
                reply = f"✅ Screenshot {url} berhasil."
            else:
                reply = f"❌ Gagal screenshot. Log: {res.stderr}"
        except Exception as e:
            reply = f"❌ Error sistem: {str(e)}"

    # 1. Handler AUTO_LIKE
    elif action == "AUTO_LIKE":
        url = value.strip().replace("twitter.com", "x.com")
        if not url.startswith("http"): url = "https://" + url
        if context: await context.bot.send_message(chat_id=user_id, text=f"🤖 Hayu Like: {url}")
        
        import subprocess
        script = f"""
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={{'width': 1920, 'height': 1080}}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('{url}', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari tombol Like...")
        like_btn = page.locator('[data-testid="like"]').first
        unlike_btn = page.locator('[data-testid="unlike"]').first
        
        if unlike_btn.is_visible():
            print("✅ Udah di-Like sebelumnya bro! ❤️")
        elif like_btn.is_visible():
            like_btn.click(force=True)
            time.sleep(3)
            print("✅ SUKSES: Berhasil di Like ngab! ❤️")
        else:
            print("❌ GAGAL: Tombol Like ga ketemu bang.")
            
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {{str(e)}}")
"""
        with open('/root/aiagent/tmp_like.py', 'w') as f: f.write(script)
        res = subprocess.run("python3.11 /root/aiagent/tmp_like.py", shell=True, capture_output=True, text=True)
        log_msg = f"{res.stdout.strip()}\n{res.stderr.strip()}".strip()
        if context: await context.bot.send_message(chat_id=user_id, text=f"📝 Laporan AUTO_LIKE:\n{log_msg}")

    # 2. Handler AUTO_RETWEET
    elif action == "AUTO_RETWEET":
        url = value.strip().replace("twitter.com", "x.com")
        if not url.startswith("http"): url = "https://" + url
        if context: await context.bot.send_message(chat_id=user_id, text=f"🤖 dalam proses bang: {url}")
        
        import subprocess
        script = f"""
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={{'width': 1920, 'height': 1080}}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('{url}', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari tombol Retweet...")
        unretweet_btn = page.locator('[data-testid="unretweet"]').first
        retweet_btn = page.locator('[data-testid="retweet"]').first
        
        if unretweet_btn.is_visible():
            print("✅ Udah di-Repost sebelumnya bro! ♻️")
        elif retweet_btn.is_visible():
            retweet_btn.click(force=True)
            time.sleep(2) 
            
            print("🔍 Mencari konfirmasi Repost...")
            confirm_btn = page.locator('[data-testid="retweetConfirm"]').first
            if confirm_btn.is_visible():
                confirm_btn.click(force=True)
                time.sleep(5)
                print("✅ SUKSES: Berhasil nge-Repost bang! ♻️")
            else:
                print("❌ GAGAL: Tombol popup Repost ga ketemu bang.")
        else:
            print("❌ GAGAL: Tombol panah Retweet ga ketemu bang.")
            
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {{str(e)}}")
"""
        with open('/root/aiagent/tmp_rt.py', 'w') as f: f.write(script)
        res = subprocess.run("python3.11 /root/aiagent/tmp_rt.py", shell=True, capture_output=True, text=True)
        log_msg = f"{res.stdout.strip()}\n{res.stderr.strip()}".strip()
        if context: await context.bot.send_message(chat_id=user_id, text=f"📝 Laporan AUTO_RETWEET:\n{log_msg}")

    # 3. Handler AUTO_POST
    elif action == "AUTO_POST":
        teks_post = value.strip()
        if context: await context.bot.send_message(chat_id=user_id, text=f"🤖 OTW nulis bang Tweetnya...")
        
        import subprocess
        script = f"""
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={{'width': 1920, 'height': 1080}}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('[https://x.com/compose/tweet](https://x.com/compose/tweet)', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari kotak ngetik...")
        textbox = page.locator('[data-testid="tweetTextarea_0"]').first
        if textbox.is_visible():
            textbox.click(force=True)
            time.sleep(1)
            page.keyboard.type('''{teks_post}''', delay=50)
            time.sleep(2)
            
            print("🔍 Mencari tombol Post...")
            post_btn = page.locator('[data-testid="tweetButton"]').first
            if post_btn.is_visible():
                post_btn.click(force=True)
                time.sleep(6)
                print("✅ SUKSES: Tweet berhasil bang! 🐦")
            else:
                print("❌ GAGAL: Tombol 'Post' ga ketemu bang.")
        else:
            print("❌ GAGAL: Kotak ngetik ga muncul bang.")
            
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {{str(e)}}")
"""
        with open('/root/aiagent/tmp_post.py', 'w') as f: f.write(script)
        res = subprocess.run("python3.11 /root/aiagent/tmp_post.py", shell=True, capture_output=True, text=True)
        log_msg = f"{res.stdout.strip()}\n{res.stderr.strip()}".strip()
        if context: await context.bot.send_message(chat_id=user_id, text=f"📝 Laporan AUTO_POST:\n{log_msg}")

    # 4. Handler AUTO_REPLY
    elif action == "AUTO_REPLY":
        parts = value.split("|", 1)
        if len(parts) < 2: return
        url = parts[0].strip().replace("twitter.com", "x.com")
        if not url.startswith("http"): url = "https://" + url
        teks_reply = parts[1].strip()
        if context: await context.bot.send_message(chat_id=user_id, text=f"🤖 On proces bang..")
        
        import subprocess
        script = f"""
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={{'width': 1920, 'height': 1080}}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('{url}', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari kotak komentar inline...")
        textbox = page.locator('[data-testid="tweetTextarea_0"]').first
        if textbox.is_visible():
            textbox.click(force=True)
            time.sleep(1)
            page.keyboard.type('''{teks_reply}''', delay=50)
            time.sleep(2)
            
            print("🔍 Mencari tombol Reply...")
            reply_btn = page.locator('[data-testid="tweetButtonInline"]').first
            if not reply_btn.is_visible():
                reply_btn = page.locator('[data-testid="tweetButton"]').first
                
            if reply_btn.is_visible():
                reply_btn.click(force=True)
                time.sleep(6)
                print("✅ SUKSES: Komentar berhasi bang! 💬")
            else:
                print("❌ GAGAL: Tombol Reply gak ketemu bang.")
        else:
            print("❌ GAGAL: Kotak komentar ga ketemu bang.")
            
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {{str(e)}}")
"""
        with open('/root/aiagent/tmp_reply.py', 'w') as f: f.write(script)
        res = subprocess.run("python3.11 /root/aiagent/tmp_reply.py", shell=True, capture_output=True, text=True)
        log_msg = f"{res.stdout.strip()}\n{res.stderr.strip()}".strip()
        if context: await context.bot.send_message(chat_id=user_id, text=f"📝 Laporan AUTO_REPLY:\n{log_msg}")

   # 5. Handler AUTO_LRT
    elif action == "AUTO_LRT":
        url = value.strip().replace("twitter.com", "x.com")
        if not url.startswith("http"): url = "https://" + url
        if context: await context.bot.send_message(chat_id=user_id, text=f"🤖 OTW Eksekusi COMBO (Like & Repost): {url}")
        
        import subprocess
        script = f"""
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={{'width': 1920, 'height': 1080}}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('{url}', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        # --- PROSES 1: LIKE ---
        print("🔍 Mengeksekusi Like...")
        like_btn = page.locator('[data-testid="like"]').first
        unlike_btn = page.locator('[data-testid="unlike"]').first
        
        if unlike_btn.is_visible():
            print("✅ LIKE: Udah di-Li sebelumnya bro! ❤️")
        elif like_btn.is_visible():
            like_btn.click(force=True)
            time.sleep(2)
            print("✅ LIKE: SUKSES nge-Like! ❤️")
        else:
            print("❌ LIKE: GAGAL, tombol Like ga ketemu.")
            
        time.sleep(2) # Jeda nafas bentar
        
        # --- PROSES 2: RETWEET ---
        print("🔍 Mengeksekusi Retweet...")
        unretweet_btn = page.locator('[data-testid="unretweet"]').first
        retweet_btn = page.locator('[data-testid="retweet"]').first
        
        if unretweet_btn.is_visible():
            print("✅ RETWEET: Udah di-Repost sebelumnya bro! ♻️")
        elif retweet_btn.is_visible():
            retweet_btn.click(force=True)
            time.sleep(2) 
            confirm_btn = page.locator('[data-testid="retweetConfirm"]').first
            if confirm_btn.is_visible():
                confirm_btn.click(force=True)
                time.sleep(4)
                print("✅ RETWEET: SUKSES nge-Repost! ♻️")
            else:
                print("❌ RETWEET: GAGAL, tombol popup Repost ga ketemu.")
        else:
            print("❌ RETWEET: GAGAL, tombol panah Retweet ga ketemu.")
            
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {{str(e)}}")
"""
        with open('/root/aiagent/tmp_lrt.py', 'w') as f: f.write(script)
        res = subprocess.run("python3.11 /root/aiagent/tmp_lrt.py", shell=True, capture_output=True, text=True)
        log_msg = f"{res.stdout.strip()}\n{res.stderr.strip()}".strip()
        if context: await context.bot.send_message(chat_id=user_id, text=f"📝 Laporan COMBO (Like + RT):\n{log_msg}")

    # 6. Handler AUTO_FOLLOW
    elif action == "AUTO_FOLLOW":
        url = value.strip().replace("twitter.com", "x.com")
        if not url.startswith("http"): url = "https://" + url
        if context: await context.bot.send_message(chat_id=user_id, text=f"🤖 OTW Follow akun: {url}")
        
        import subprocess
        script = f"""
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={{'width': 1920, 'height': 1080}}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('{url}', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari tombol Follow...")
        # Trik nangkep tombol follow Twitter yang ID-nya dinamis
        unfollow_btn = page.locator('button[data-testid$="-unfollow"]').first
        follow_btn = page.locator('button[data-testid$="-follow"]').first
        
        if unfollow_btn.is_visible():
            print("✅ Udah lu Follow sebelumnya bro! 🤝")
        elif follow_btn.is_visible():
            follow_btn.click(force=True)
            time.sleep(3)
            print("✅ SUKSES: Berhasil nge-Follow! 👤+")
        else:
            # Backup plan kalau tombol utama disembunyiin
            alt_follow = page.locator('button[role="button"]:has-text("Follow")').first
            if alt_follow.is_visible()            alt_follow.click(force=True)
                time.sleep(3)
                print("✅ SUKSES: Berhasil nge-Follow (Alternatif)! 👤+")
            else:
                print("❌ GAGAL: Tombol Follow ga ketemu.")
                
        browser.close()
except Exception as e:
    print(f"❌ CRASH: {{str(e)}}")
"""
        with open('/root/aiagent/tmp_follow.py', 'w') as f: f.write(script)
        res = subprocess.run("python3.11 /root/aiagent/tmp_follow.py", shell=True, capture_output=True, text=True)
        log_msg = f"{res.stdout.strip()}\n{res.stderr.strip()}".strip()
        if context: await context.bot.send_message(chat_id=user_id, text=f"📝 Laporan AUTO_FOLLOW:\n{log_msg}")

    # 1. Handler CREATE_FILE (Bikin file baru)
    elif action == "CREATE_FILE":
        parts = value.split("|", 1)
        if len(parts) < 2:
            if context: await context.bot.send_message(chat_id=user_id, text="❌ Format: CREATE_FILE: nama.py | kodenya")
            return
        filename, code = parts[0].strip(), parts[1].strip()
        filepath = f"/root/aiagent/{filename}"
        try:
            with open(filepath, 'w') as f: f.write(code)
            if context: await context.bot.send_message(chat_id=user_id, text=f"✅ File `{filename}` berhasil dibuat!")
        except Exception as e:
            if context: await context.bot.send_message(chat_id=user_id, text=f"❌ Gagal: {str(e)}")

    # 2. Handler SUPER_FIX (Benerin & Ketik Ulang File di VPS)
    elif action == "SUPER_FIX":
        parts = value.split("|", 1)
        if len(parts) < 2:
            if context: await context.bot.send_message(chat_id=user_id, text="❌ Format: SUPER_FIX: file.py | errornya")
            return
        filename, error_msg = parts[0].strip(), parts[1].strip()
        filepath = f"/root/aiagent/{filename}"
        if not os.path.exists(filepath):
            if context: await context.bot.send_message(chat_id=user_id, text="❌ Filenya ga ada bro.")
            return
        with open(filepath, 'r') as f: broken_code = f.read()
        if context: await context.bot.send_message(chat_id=user_id, text=f"🏥 Lagi operasi bedah `{filename}`...")
        
        prompt_fix = f"Tolong benerin kode ini agar tidak error: {error_msg}\n\nKODE:\n{broken_code}\n\nBerikan HANYA kode murni tanpa penjelasan."
        fixed_code = await run_agent(user_id, prompt_fix, context)
        # 🔥 FITUR BARU: Bersihkan kodingan dari markdown blok
        clean_code = fixed_code.replace("```python", "").replace("```", "").strip()
        
        try:
            with open(filepath, 'w') as f: f.write(clean_code)
            if context: await context.bot.send_message(chat_id=user_id, text=f"✅ `{filename}` udah sehat & diketik ulang!")
        except Exception as e:
            if context: await context.bot.send_message(chat_id=user_id, text=f"❌ Gagal fix: {str(e)}")

    # 3. Handler DEBUG_CHAT (Konsultasi Kode dari VS Code/Luar)
    elif action == "DEBUG_CHAT":
        parts = value.split("|", 1)
        if len(parts) < 2:
            if context: await context.bot.send_message(chat_id=user_id, text="❌ Format: DEBUG_CHAT: error | kodenya")
            return
        user_err, user_code = parts[0].strip(), parts[1].strip()
        if context: await context.bot.send_message(chat_id=user_id, text="👨‍💻 AI lagi nganalisa kodingan lu...")
        
        prompt_debug = f"User buntu ngoding. Error: {user_err}\nKode: {user_code}\nJelaskan singkat letak salahnya pakai bahasa santai 'bro' dan kasih kode benernya."
        answer = await run_agent(user_id, prompt_debug, context)
        if context: await context.bot.send_message(chat_id=user_id, text=f"🏥 ANALISA AI:\n\n{answer}", parse_mode="Markdown")

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

            # Extract stock code
            stock_codes = re.findall(r'\b[A-Z]{2,7}\b', user_message.upper())
            kata_sampah = {
                'TOLONG', 'ANALISA', 'ANALISIS', 'SEKARANG', 'PAKAI', 'MENGGUNAKAN', 
                'SKILL', 'KOIN', 'SAHAM', 'CRYPTO', 'WAKTU', 'SAAT', 'WIB', 'INI', 
                'SISTEM', 'TANGGAL', 'JAM', 'DONG', 'COBA', 'KASIH', 'LIHAT', 'CEK',
                'HARI', 'MARKET', 'GOLD', 'FOREX', 'BUAT', 'YANG', 'DARI', 'PADA'
            }
            stock_code = next((s for s in stock_codes if s not in kata_sampah), "BBCA")

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

            # 🔥 INJEKSI PESAN USER KE DALAM SKILL 🔥
            code = f"PESAN_USER = {repr(user_message)}\n" + code

            reply = execute_skill(skill_name, code)
            
            # 🔥 AUTO-SEND JIKA OFFICE ENGINE YANG JALAN 🔥
            if skill_name == "universal_office_engine":
                await handle_file_delivery(user_id, context)

        except Exception as e:
            reply = f"❌ Error eksekusi skill: {str(e)}"

    add_message(user_id, "assistant", reply)
    return reply
