import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_TOKEN
from agent import run_agent
from memory import clear_history, get_all_memories_text
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from morning_briefing import generate_morning_briefing
import auto_trader
import pytz
import os
import tempfile

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Gua personal AI assistant lo 🤖\n\n"
        "Gua bisa bantu:\n"
        "📧 Kirim & baca email\n"
        "📅 Buat event di Google Calendar\n"
        "🔍 Research & web search\n"
        "🎙️ Voice note\n"
        "📄 Baca PDF, Word, Excel\n"
        "🧠 Inget semua tentang lo\n\n"
        "Commands:\n"
        "/start - Mulai\n"
        "/clear - Hapus history chat\n"
        "/memory - Lihat semua memory\n\n"
        "Ketik, kirim voice note, atau upload file!"
    )

async def send_morning_briefing(app):
    """Kirim morning briefing ke semua user"""
    from memory import get_all_user_ids
    try:
        briefing = await generate_morning_briefing()
        # Kirim ke user ID lo — ganti dengan Telegram user ID lo
        USER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0"))
        if USER_ID:
            await app.bot.send_message(
                chat_id=USER_ID,
                text=briefing,
                parse_mode='Markdown'
            )
            print(f"✅ Morning briefing terkirim ke {USER_ID}")
    except Exception as e:
        print(f"❌ Gagal kirim morning briefing: {str(e)}")

async def handle_trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("trade_yes_"):
        parts = data.split("_")
        symbol = parts[2]
        side = parts[3]
        sl = float(parts[4])
        tp = float(parts[5])
        qty = float(parts[6])

        await query.edit_message_text(f"⏳ Executing {side} {symbol}...")

        from tools.binance_trader import open_position
        result = open_position(
            symbol=symbol,
            side=side,
            usdt_amount=qty,
            sl_price=sl,
            tp_price=tp,
            leverage=5
        )

        if "error" in result:
            await query.edit_message_text(f"❌ Error: {result['error']}")
        else:
            await query.edit_message_text(
                f"✅ <b>ORDER EXECUTED!</b>\n\n"
                f"📊 {result['symbol']} {result['side']}\n"
                f"💰 Entry: ${result['entry']:,}\n"
                f"🛑 SL: ${result['sl']:,}\n"
                f"✅ TP: ${result['tp']:,}\n"
                f"📦 Qty: {result['qty']}",
                parse_mode="HTML"
            )

    elif data.startswith("trade_no_"):
        symbol = data.split("_")[2]
        await query.edit_message_text(f"❌ Trade {symbol} di-skip.")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_history(update.effective_user.id)
    await update.message.reply_text("✅ History chat udah dihapus!")

async def show_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(get_all_memories_text(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    os.environ['USER_CHAT'] = user_message
    waktu_sekarang = datetime.datetime.now().strftime("%H:%M WIB (Tanggal %d %B %Y)")
    user_message = f"{user_message}\n\n[Sistem: Waktu saat ini {waktu_sekarang}]"

    await update.message.reply_chat_action("typing")
    try:
        reply = await run_agent(user_id, user_message, context)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"❌ Terjadi error: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_chat_action("typing")
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)

        from groq import Groq
        from config import GROQ_API_KEY
        groq_client = Groq(api_key=GROQ_API_KEY)
        with open(tmp_path, 'rb') as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=("voice.ogg", audio_file),
                model="whisper-large-v3",
                language="id",
            )
        os.unlink(tmp_path)

        user_message = transcription.text
        await update.message.reply_text(f"🎙️ Lo bilang: \"{user_message}\"")
        reply = await run_agent(user_id, user_message)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal proses voice note: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_chat_action("typing")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp_path = f"/tmp/photo_{user_id}_{timestamp}.jpg"
        await file.download_to_drive(tmp_path)
        caption = update.message.caption or ""
        user_message = caption if caption else "tolong analisa gambar ini"
        reply = await run_agent(user_id, user_message, context)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal proses gambar: {str(e)}")

async def switch_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return

    args = context.args
    if not args or args[0] not in ["scalping", "swing"]:
        await update.message.reply_text(
            "⚙️ Cara pakai:\n"
            "/mode scalping\n"
            "/mode swing"
        )
        return

    mode = args[0]
    auto_trader.TRADING_MODE = mode

    if mode == "scalping":
        auto_trader.TIMEFRAME = "15m"
        auto_trader.ATR_MULT = 1.5
        auto_trader.RSI_LONG_MIN = 45
        auto_trader.RSI_LONG_MAX = 65
        auto_trader.RSI_SHORT_MIN = 35
        auto_trader.RSI_SHORT_MAX = 55
        auto_trader.CHECK_INTERVAL = 300
        auto_trader.MODE_LABEL = "⚡ SCALPING (15m)"
    else:
        auto_trader.TIMEFRAME = "4h"
        auto_trader.ATR_MULT = 2.5
        auto_trader.RSI_LONG_MIN = 50
        auto_trader.RSI_LONG_MAX = 70
        auto_trader.RSI_SHORT_MIN = 30
        auto_trader.RSI_SHORT_MAX = 50
        auto_trader.CHECK_INTERVAL = 3600
        auto_trader.MODE_LABEL = "🌊 SWING (4h)"

    await update.message.reply_text(
        f"✅ Mode berhasil diganti ke <b>{auto_trader.MODE_LABEL}</b>",
        parse_mode="HTML"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_chat_action("typing")

    try:
        if update.message.document:
            doc = update.message.document
            file_name = doc.file_name.lower()
            file = await context.bot.get_file(doc.file_id)
        else:
            await update.message.reply_text("❌ Format file tidak didukung.")
            return

        if not any(file_name.endswith(ext) for ext in ['.pdf', '.docx', '.xlsx', '.xls']):
            await update.message.reply_text(
                "❌ File tidak didukung.\n"
                "Format yang bisa dibaca: PDF, Word (.docx), Excel (.xlsx)"
            )
            return

        caption = update.message.caption or ""

        cleanup_keywords = ["rapihin", "rapiin", "bersihkan", "clean", "cleanup",
                            "beresin", "perbaiki", "format", "rapi"]
        is_cleanup = any(kw in caption.lower() for kw in cleanup_keywords)

        if file_name.endswith(('.xlsx', '.xls')) and is_cleanup:
            await update.message.reply_text(
                f"📂 File diterima: {doc.file_name}\n⏳ Lagi rapihin Excel lo..."
            )

            import tempfile
            with tempfile.NamedTemporaryFile(
                suffix='.xlsx', delete=False
            ) as tmp:
                tmp_path = tmp.name
            await file.download_to_drive(tmp_path)

            from tools.file_creator import clean_excel
            output_path = clean_excel(tmp_path, caption)
            os.unlink(tmp_path)

            if isinstance(output_path, str) and output_path.startswith("❌"):
                await update.message.reply_text(output_path)
            else:
                with open(output_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=f,
                        filename=f"rapi_{doc.file_name}",
                        caption="✅ Excel udah dirapiin bro!"
                    )
            return

        await update.message.reply_text(
            f"📂 File diterima: {doc.file_name}\n⏳ Lagi dibaca..."
        )

        import tempfile
        with tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(file_name)[1],
            delete=False
        ) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)

        extracted_text = ""

        if file_name.endswith('.pdf'):
            import fitz
            doc_pdf = fitz.open(tmp_path)
            for page in doc_pdf:
                extracted_text += page.get_text()
            doc_pdf.close()

        elif file_name.endswith('.docx'):
            from docx import Document
            doc_word = Document(tmp_path)
            for para in doc_word.paragraphs:
                if para.text.strip():
                    extracted_text += para.text + "\n"

        elif file_name.endswith(('.xlsx', '.xls')):
            import openpyxl
            wb = openpyxl.load_workbook(tmp_path, data_only=True)
            for sheet in wb.worksheets:
                extracted_text += f"\n[Sheet: {sheet.title}]\n"
                for row in sheet.iter_rows(values_only=True):
                    row_data = [str(cell) if cell is not None else "" for cell in row]
                    if any(cell.strip() for cell in row_data):
                        extracted_text += " | ".join(row_data) + "\n"

        os.unlink(tmp_path)

        if not extracted_text.strip():
            await update.message.reply_text("❌ File kosong atau tidak bisa dibaca.")
            return

        extracted_text = extracted_text[:4000]
        user_message = f"{caption}\n\n[ISI FILE: {doc.file_name}]\n{extracted_text}" if caption else f"[ISI FILE: {doc.file_name}]\n{extracted_text}"

        reply = await run_agent(user_id, user_message, context)
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"❌ Gagal baca file: {str(e)}")

async def manual_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Generating morning briefing... tunggu sebentar!")
    briefing = await generate_morning_briefing()
    await update.message.reply_text(briefing, parse_mode='Markdown')

def main():
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0,
    )
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).request(request).build()

    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Jakarta'))
    scheduler.add_job(
        send_morning_briefing,
        'cron',
        hour=7,
        minute=0,
        args=[app]
    )
    scheduler.start()
    print("✅ Scheduler morning briefing aktif — jam 07.00 WIB")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("memory", show_memory))
    app.add_handler(CommandHandler("briefing", manual_briefing))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(handle_trade_callback, pattern="^trade_"))
    app.add_handler(CommandHandler("mode", switch_mode))

    print("Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
