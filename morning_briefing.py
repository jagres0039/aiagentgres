from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from groq import Groq
from tools.search_tool import web_search

from config import GROQ_API_KEY, GROQ_MODEL

client = Groq(api_key=GROQ_API_KEY)

async def generate_morning_briefing() -> str:
    today = datetime.now().strftime("%A, %d %B %Y")

    searches = {
        "ihsg": "IHSG Jakarta composite index today 2026",
        "btc": "Bitcoin BTC price USD today 2026",
        "eth": "Ethereum ETH price USD today 2026",
        "sol": "Solana SOL price USD today 2026",
        "xau": "XAU gold spot price USD today 2026",
        "silver": "Silver spot price USD today 2026",
        "forex": "EUR/USD GBP/USD USD/JPY GBP/JPY forex rate today 2026",
        "news": "berita ekonomi Indonesia global terkini hari ini 2026",
        "calendar": f"economic calendar forex high impact news today {datetime.now().strftime('%B %Y')}",
        "sholat": "jadwal waktu sholat Cicurug Sukabumi hari ini",
    }

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(web_search, q): k for k, q in searches.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = f"Data tidak tersedia: {str(e)}"

    prompt = f"""Buat morning briefing finansial yang rapi dan informatif untuk tanggal {today}.
Gunakan HANYA data yang tersedia di bawah — ambil angka/harga yang paling relevan.

DATA TERSEDIA:
IHSG: {results.get('ihsg', '')[:300]}
BTC: {results.get('btc', '')[:300]}
ETH: {results.get('eth', '')[:300]}
SOL: {results.get('sol', '')[:300]}
XAU/Gold: {results.get('xau', '')[:300]}
Silver: {results.get('silver', '')[:300]}
Forex: {results.get('forex', '')[:300]}
Berita Ekonomi: {results.get('news', '')[:500]}
Economic Calendar: {results.get('calendar', '')[:300]}
Waktu Sholat: {results.get('sholat', '')[:300]}

INSTRUKSI FORMAT:
- Tulis morning briefing dengan format di bawah
- Isi setiap bagian dengan data yang tersedia
- Kalau data tidak ada, skip bagian itu jangan tulis N/A
- JANGAN tulis catatan, disclaimer, atau penjelasan di akhir
- JANGAN tulis (N/A) di manapun
- Selesai setelah bagian waktu sholat

FORMAT WAJIB:
🌅 *MORNING BRIEFING — {today}*
━━━━━━━━━━━━━━━━━━━

🇮🇩 *IHSG*
- [tulis harga IHSG dari data]

₿ *CRYPTO*
- BTC: [harga dari data]
- ETH: [harga dari data]
- SOL: [harga dari data]

🥇 *KOMODITAS*
- XAU/USD: [harga dari data]
- Silver: [harga dari data]

💱 *FOREX*
- EUR/USD: [rate dari data]
- GBP/USD: [rate dari data]
- USD/JPY: [rate dari data]
- GBP/JPY: [rate dari data]

📰 *BERITA EKONOMI*
- [berita 1 dari data]
- [berita 2 dari data]
- [berita 3 dari data]

📅 *ECONOMIC CALENDAR HARI INI*
- [event dari data]

🕐 *WAKTU SHOLAT CICURUG*
- Subuh: [jam] | Dzuhur: [jam]
- Ashar: [jam] | Maghrib: [jam]
- Isya: [jam]
━━━━━━━━━━━━━━━━━━━"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """Kamu membuat morning briefing finansial yang akurat dan rapi.
WAJIB:
- Gunakan HANYA angka/data yang ada di hasil search
- Kalau data tidak tersedia untuk suatu item, skip saja jangan tulis N/A
- Format output harus rapi dengan emoji
- Bahasa Indonesia santai
DILARANG:
- Jangan tulis (N/A) dimanapun
- Jangan tulis catatan, disclaimer, atau penjelasan di akhir
- Jangan tambah teks apapun setelah section waktu sholat
- Jangan karang angka sendiri"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Gagal generate morning briefing: {str(e)}"
