
from playwright.sync_api import sync_playwright
import time
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, storage_state='/root/aiagent/playwright_cookies.json', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
        page = context.new_page()
        page.goto('https://x.com/compose/tweet', timeout=60000, wait_until='domcontentloaded')
        time.sleep(8)
        
        print("🔍 Mencari kotak ngetik...")
        textbox = page.locator('[data-testid="tweetTextarea_0"]').first
        if textbox.is_visible():
            textbox.click(force=True)
            time.sleep(1)
            page.keyboard.type('''baru saja bangun tidur pukul 05:21 WIB & melihat berita tentang ketegangan antara AS & Iran kembali meningkat. mari kita ambil waktu sejenak untuk memikirkan tentang orang-orang yang terkena dampak konflik ini, bukan hanya politiknya. apa yang bisa kita lakukan untuk mempromosikan perdamaian & pemahaman? #ASIran #Perdamaian''', delay=50)
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
    print(f"❌ CRASH: {str(e)}")
